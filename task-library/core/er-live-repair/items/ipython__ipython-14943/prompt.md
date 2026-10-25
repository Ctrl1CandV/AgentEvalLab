## Issue (ipython/ipython)

Invalid completions shown when evaluation policy forbids access
To reproduce create a `repro.py` file with:

```python
class StringMethods:
    def a():
        pass

class Test:
     def __init__(self):
         self.str = StringMethods()
     def __getattr__(self, name):
         raise AttributeError(f"{name} not found")
```

Then in IPython:

```python
%config Completer.use_jedi = False
from repro import Test
r = Test()
r.str.# <tab>
```

This will show all methods of `str`, but none of `StringMethods`.

This is because:
- the custom `__getattr__` leads the default guarded evaluation policy to reject evaluation of `r.str`, which raises `GuardRejection`
- IPython then tries to recover from any `Exception` by trimming the `r.` part away, even though it might be sufficient to trim on `SyntaxError` and related exceptions:

https://github.com/ipython/ipython/blob/d47970f7097668ec89a47120e14625d44b617d68/IPython/core/completer.py#L1300-L1324

Allow evaluation of attributes from given (trusted) library
It is currently possible to use the limited evaluation policy with `policy_overrides` but it is often cumbersome when multiple overrides need to be added, e.g. to relax `allowed_getattr_external` for three classes `A`, `B` and `C` defined in `my_trusted_library" one currently needs to define:

```python
c.Completer.policy_overrides = {
    "allowed_getattr_external": {
        ("my_trusted_library", "A"),
        ("my_trusted_library", "B"),
        ("my_trusted_library", "C"),
    }
}
```

We could relax the rules to allow to specify:

```python
c.Completer.policy_overrides = {
    "allowed_getattr_external": {
        ("my_trusted_library", ),
    }
}
```

which would make allow everything under given namespace.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.

## Names the tests use

The project's tests for this issue use these names; give them exactly as listed:

- An entry of `allowed_getattr_external` (in `Completer.policy_overrides` and in evaluation policies) may also name a whole module, as a dotted string (`"my.safe.lib"`) or a one-element tuple (`("my_trusted_library",)`); it allows attribute access on instances of every class defined in that module or below it.
