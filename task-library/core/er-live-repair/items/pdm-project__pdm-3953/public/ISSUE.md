`pdm publish` does not send License-Expression or License-File to the index

`pdm publish` builds the upload form in `PackageFile.metadata_dict`, and the only license field it sends is the legacy `License`. With core metadata 2.4 (PEP 639) the license is in `License-Expression`, and neither that nor `License-File` is ever sent.

PyPI takes the license from the upload form, not from the file (see the TODO above `metadata.parse` in warehouse's `forklift/legacy.py`), so a PEP 639 package released with `pdm publish` shows no license on PyPI.

pdm itself is one. 2.29.3 was released with `pdm publish --no-build`, and the wheel METADATA has:

```
Metadata-Version: 2.4
License-Expression: MIT
License-File: LICENSE
```

but https://pypi.org/pypi/pdm/2.29.3/json has `"license": ""` and `"license_expression": null`. unearth, also MIT under PEP 639, shows `"license_expression": "MIT"`.

twine sends these as `license_expression` and `license_file`. It skips `License-File` when Metadata-Version is below 2.4, because setuptools writes that field under 2.1 as well.
