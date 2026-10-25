Deprecate `isolated_filesystem()`

As @davidism pointed out in https://github.com/pallets/click/issues/3123#issuecomment-3433922728 :

> Nowadays you can also use `pytest` directly for this, or use with `tempfile.TemporaryDirectory()`. I don't think we'd add `isolated_filesystem` today, I think it was added before Python 3 and `pytest` were in common use.

Relates to: https://github.com/pallets/click/issues/3501
