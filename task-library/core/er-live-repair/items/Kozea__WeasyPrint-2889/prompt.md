## Issue (Kozea/WeasyPrint)

BUG: break-after:avoid ignored for table rows in certain situations

According to the Weasyprint documentation, `break-before` and `break-after` are supported for pages:
https://doc.courtbouillon.org/weasyprint/stable/api_reference.html#css-fragmentation-module-level-3-4

I am not sure whether this is true especially for table elements. I am currently trying to avoid page breaks between certain table rows with different methods, but I have no success. This is what I have tried so far (only the relevant fragments):

Styles:
```
tr.main { break-after: avoid; }
tr.main td { break-after: avoid; }
```

HTML:
```
...
<table>
<tbody>
<tr class="main"><td>m1</td><td>m2></td></tr>
<tr class="detail"><td>d1</td><td>d2></td></tr>
... <!-- many repetitions of the above two lines here, so that the table takes more than one page -->
<tr class="main"><td>m1</td><td>m2></td></tr>
<tr class="detail"><td>d1</td><td>d2></td></tr>
</tbody>
</table>
...
```

The problem is that Weasyprint happily inserts a page break between a "main" and a "detail" table row, despite the CSS which should avoid such breaks.

I have to admit that it's not clear to me whether or not break avoids should work when applied to table elements. Some articles on the web state that they should work, some state that they shouldn't, and some state the browser support varies.

According to my own tests, they work in modern browsers. For example, in my tests, neither Chromium nor Firefox in Linux did page-break the table between a "main" and a "detail" row. But Weasyprint did.

Before eventually reporting a bug, I'd like to know what Weasyprint is expected to do in such situations.

Thank you very much in advance!

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
