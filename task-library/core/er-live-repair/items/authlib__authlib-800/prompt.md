## Issue (authlib/authlib)

`id_token` generation does not work with `EdDSA`
It seems `id_token` generation is broken with `EdDSA` jwks.

The `create_half_hash` method is called in the `generate_id_token` method:

https://github.com/authlib/authlib/blob/c9890da9d1f1d5fd7bf551e7cd28facfc64e9b7d/authlib/oidc/core/grants/util.py#L102-L107

However, it seems it does not support `EdDSA` keys:

```python
>>> from authlib.oidc.core.util import create_half_hash
>>> assert create_half_hash("test", "RS256")
>>> assert create_half_hash("test", "EdDSA")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
AssertionError
```

After investigation, it seems this is because authlib tries to access `hashlib.shaDSA`, which does not exist:

https://github.com/authlib/authlib/blob/c9890da9d1f1d5fd7bf551e7cd28facfc64e9b7d/authlib/oidc/core/util.py#L7-L14

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
