# Scoring Map: eng-004

| Requirement | Private checks | Sample coverage | Critical |
| --- | --- | --- | --- |
| REQ-SEARCH: filtering, Unicode code-point order, default/explicit pagination, total and nextOffset | search-filter, default-pagination, unicode-codepoint-order, pagination-boundaries | trimming, case folding, tag/title search, Unicode IDs that catch UTF-16 ordering mistakes, defaults, later pages, empty out-of-range pages, zero matches | Yes |
| REQ-INPUT: reject blank queries, invalid numbers, unknown/repeated options | invalid-pagination | Six invalid CLI combinations | Yes |
| REQ-CSV: quoting, escaped quotes, CR/LF, CRLF | csv-rfc4180 | Commas, quotes, multiline values, empty tags | Yes |
| REQ-REGRESSION: preserve complete records, rank zero, empty arrays | index-compatibility | Exact comparison with a fixed hidden catalog | Yes |

Checks use actual CLI output and errors. Internal algorithms and filenames are not scored. Evidence stores summaries, bounded output previews, or hashes rather than full candidate streams.
