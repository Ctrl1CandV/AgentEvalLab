#!/usr/bin/env python3
"""Run one untrusted command inside a bubblewrap sandbox.

Used by the harness (execute_command, command checks) and by task graders and
public checkers whenever they start candidate code. Inside the sandbox:

- only the --rw directories are writable, at the same absolute paths;
- system directories and the active Python/Node runtimes are read-only;
- there is no /home (apart from runtime prefixes), no network, a private /tmp,
  and separate PID/IPC/UTS namespaces, so killing the launcher ends every
  process the command started.

Usage:
  sandbox_exec.py --rw DIR [--rw DIR ...] [--ro DIR ...] -- COMMAND [ARG ...]
  sandbox_exec.py --check

The launcher replaces itself with bwrap, so the command's exit status is
returned unchanged. Exit status 125 means the sandbox could not be prepared.
"""
import argparse
import os
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


def bwrap_arguments(bwrap, writable, readable, command):
    arguments = [bwrap, "--unshare-all", "--die-with-parent", "--new-session",
                 "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for path in SYSTEM_READ_ONLY:
        arguments += ["--ro-bind-try", path, path]
    for path in runtime_prefixes() + readable:
        arguments += ["--ro-bind", path, path]
    for path in writable:
        arguments += ["--bind", path, path]
    cwd = os.path.realpath(os.getcwd())
    inside = any(cwd == path or cwd.startswith(path + "/") for path in writable + readable)
    arguments += ["--chdir", cwd if inside else writable[0]]
    for name in ("HOME", "TMPDIR", "TMP", "TEMP"):
        arguments += ["--setenv", name, "/tmp"]
    return arguments + ["--", *command]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rw", action="append", default=[], type=absolute_directory)
    parser.add_argument("--ro", action="append", default=[], type=absolute_directory)
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
        os.execv(bwrap, bwrap_arguments(bwrap, writable, args.ro, command))
    except OSError as error:
        print("SANDBOX_UNAVAILABLE: " + error.strerror, file=sys.stderr)
        return SETUP_FAILED


if __name__ == "__main__":
    sys.exit(main())
