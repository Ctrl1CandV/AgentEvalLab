## Issue (pdm-project/pdm)

`pdm show` and `pdm list` show no license for packages that use License-Expression

`pdm show` and the `licenses` field of `pdm list` only read the `License` core metadata field. Packages built with metadata 2.4 (PEP 639) put an SPDX expression in `License-Expression` instead, and usually drop the license classifiers as well, so both commands show nothing for them. packaging, idna and urllib3 are already published this way.

```
$ pdm add packaging==26.3 requests==2.32.3
$ pdm list --fields name,version,licenses
╭────────────────────┬────────────┬────────────╮
│ name               │ version    │ licenses   │
├────────────────────┼────────────┼────────────┤
│ certifi            │ 2026.10.19 │ MPL-2.0    │
│ charset-normalizer │ 3.5.2      │ MIT        │
│ idna               │ 3.20       │            │
│ packaging          │ 26.3       │            │
│ requests           │ 2.32.3     │ Apache-2.0 │
│ urllib3            │ 2.8.0      │            │
╰────────────────────┴────────────┴────────────╯
```

`pdm show packaging` has an empty `License:` row too. The installed METADATA for packaging 26.3 has `Metadata-Version: 2.4` and `License-Expression: Apache-2.0 OR BSD-2-Clause`, with no `License` field and no license classifier.

Same thing for the current project: with `license = "MIT"` in pyproject.toml (what `pdm init` writes now), the built metadata only has `License-Expression: MIT`, and `pdm show` and `pdm show --license` print an empty license.

I'd read `License-Expression` first and fall back to `License`, in `ProjectInfo.from_distribution` and in `Listable`.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
