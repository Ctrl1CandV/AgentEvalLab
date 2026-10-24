#!/usr/bin/env python3
"""Run one untrusted command inside a bubblewrap sandbox.

Used by the harness (execute_command, command checks) and by task graders and
public checkers whenever they start candidate code. Inside the sandbox:

- only the --rw directories are writable, at the same absolute paths;
- system directories and the active Python/Node runtimes are read-only;
- there is no /home (apart from runtime prefixes), no network, a private /tmp,
  and separate PID/IPC/UTS namespaces, so killing the launcher ends every
  process the command started;
- a task's runtime mounts (--mount SOURCE:TARGET) are bound read-only at their
  fixed TARGET under /runtime, and --env NAME=VALUE sets the environment that
  goes with them (PLAN-007 WP2.4).

Usage:
  sandbox_exec.py --rw DIR [--rw DIR ...] [--ro DIR ...] [--mount SOURCE:TARGET ...] [--env NAME=VALUE ...] -- COMMAND [ARG ...]
  sandbox_exec.py --check

The launcher replaces itself with bwrap, so the command's exit status is
returned unchanged. Exit status 125 means the sandbox could not be prepared.
"""
import argparse
import os
import re
import shutil
import sys

SYSTEM_READ_ONLY = ("/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/etc")
SETUP_FAILED = 125


def runtime_prefixes():
    """Install prefixes of the interpreters candidates may need, outside the system tree."""
    prefixes = set()
    for executable in (sys.executable, shutil.which("python3"), shutil.which("node")):
        if not executable:
            continue
        prefix = os.path.dirname(os.path.dirname(os.path.realpath(executable)))
        if prefix != "/usr" and not any(prefix == path or prefix.startswith(path + "/") for path in SYSTEM_READ_ONLY):
            prefixes.add(prefix)
    return sorted(prefixes)


def absolute_directory(value):
    path = os.path.realpath(value)
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError("not a directory: " + value)
    return path


def runtime_mount(value):
    """SOURCE:TARGET, a directory bound read-only at a fixed path under /runtime."""
    source, separator, target = value.rpartition(":")
    if not separator or not re.fullmatch(r"/runtime(/[A-Za-z0-9._-]+)+", target) or "/../" in target + "/" or "/./" in target + "/":
        raise argparse.ArgumentTypeError("a mount is SOURCE:/runtime/NAME: " + value)
    return absolute_directory(source), target


def environment(value):
    name, separator, setting = value.partition("=")
    if not separator or not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,63}", name) or name in ("HOME", "TMPDIR", "TMP", "TEMP"):
        raise argparse.ArgumentTypeError("an environment setting is NAME=VALUE: " + value)
    return name, setting


def bwrap_arguments(bwrap, writable, readable, command, mounts=(), env=()):
    arguments = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                 "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for path in SYSTEM_READ_ONLY:
        arguments += ["--ro-bind-try", path, path]
    for path in runtime_prefixes() + readable:
        arguments += ["--ro-bind", path, path]
    for path in writable:
        arguments += ["--bind", path, path]
    for source, target in mounts:
        arguments += ["--ro-bind", source, target]
    cwd = os.path.realpath(os.getcwd())
    inside = any(cwd == path or cwd.startswith(path + "/") for path in writable + readable)
    arguments += ["--chdir", cwd if inside else writable[0]]
    for name in ("HOME", "TMPDIR", "TMP", "TEMP"):
        arguments += ["--setenv", name, "/tmp"]
    for name, setting in env:
        arguments += ["--setenv", name, setting]
    return arguments + ["--", *command]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rw", action="append", default=[], type=absolute_directory)
    parser.add_argument("--ro", action="append", default=[], type=absolute_directory)
    parser.add_argument("--mount", action="append", default=[], type=runtime_mount)
    parser.add_argument("--env", action="append", default=[], type=environment)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command

    bwrap = shutil.which("bwrap")
    if not bwrap:
        print("SANDBOX_UNAVAILABLE: bwrap not found", file=sys.stderr)
        return SETUP_FAILED
    if args.check:
        writable, command = [os.path.realpath(os.getcwd())], ["true"]
    else:
        writable = args.rw
        if not writable or not command:
            parser.error("--rw and a command are required")
    try:
        os.execv(bwrap, bwrap_arguments(bwrap, writable, args.ro, command, args.mount, args.env))
    except OSError as error:
        print("SANDBOX_UNAVAILABLE: " + error.strerror, file=sys.stderr)
        return SETUP_FAILED


if __name__ == "__main__":
    sys.exit(main())
