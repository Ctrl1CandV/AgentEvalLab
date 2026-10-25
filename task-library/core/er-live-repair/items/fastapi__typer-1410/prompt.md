## Issue (fastapi/typer)

Argument(metavar="MY_ARG") has different meaning for the arguments panel compared to the usage text or the non-rich help output


### Discussed in https://github.com/fastapi/typer/discussions/646

<div type='discussions-op-text'>

<sup>Originally posted by **JacobKochems** August  1, 2023</sup>
First of all, thanks to all who are involved, especially to the creator, for your hard work. It's really a cool project.

### First Check

- [x] I added a very descriptive title here.
- [X] I used the GitHub search to find a similar question and didn't find it.
- [X] I searched the Typer documentation, with the integrated search.
- [X] I already searched in Google "How to X in Typer" and didn't find any information.
- [X] I already read and followed all the tutorial in the docs and didn't find an answer.
- [X] I already checked if it is not related to Typer but to [Click](https://github.com/pallets/click).

### Commit to Help

- [X] I commit to help with one of those options 👆

### Example Code

```python
# mre.py  (minimal reproducible example)

import typer
from typing_extensions import Annotated

app = typer.Typer()


@app.command()
def show(user: Annotated[str, typer.Argument(metavar="MY_ARG")]):
    """Show user."""
    typer.echo(f"[stub] show user: {user}")


if __name__ == '__main__':
    app()
```


### Description

### Observed Behavior
With rich installed, calling the above example with `python mre.py --help` produces the following help output:

```
Usage: mre.py [OPTIONS] MY_ARG                                                                                                                                                                  
                                                                                                                                                                                                   
 Show user.                                                                                                                                                                                        
                                                                                                                                                                                                   
╭─ Arguments ──────────────────────────────────────────────────
│ *    user      MY_ARG  [default: None] [required]
╰────────────────────────────────────────────────────────
╭─ Options ───────────────────────────────────────────────────
│ --install-completion  Install completion for the current shell.
│ --show-completion     Show completion for the current shell, to copy it or customize the installation.
│ --help                Show this message and exit.
╰────────────────────────────────────────────────────────
```
In the usage text `MY_ARG` stands for the argument _name_ but in the argument panel it stands for the argument _type_, thereby rendering this solution: https://github.com/tiangolo/typer/issues/230#issuecomment-774510743 invalid for rich help text output.
Moreover, the argument _type_ can only be set/overwritten by `metavar` if `metavar!="user".upper()`, which seems to be related to #438.

Without rich being installed the above example looks like this:
```
Usage: mre.py [OPTIONS] MY_ARG

  Show user.

Arguments:
  MY_ARG  [required]

Options:
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.
```
and works as expected: in both places `MY_ARG` stands for the argument _name_ and the argument _type_ vanishes.

### Expected Behavior
I expect the respective argument _names_ `user`/`USER` to be replaced by `metavar` regardless of output mode and the argument _type_ to stay unchanged.

### Operating System

Linux

### Operating System Details

_No response_

### Typer Version

0.9.0

### Python Version

3.9.2

### Additional Context

_No response_</div>

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
