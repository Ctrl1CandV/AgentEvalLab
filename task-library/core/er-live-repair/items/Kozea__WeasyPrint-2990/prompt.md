## Issue (Kozea/WeasyPrint)

A link that is a flex item gets no link annotation

**Version:** WeasyPrint 70.0 (macOS 26.7)

A link that is itself a flex item produces no link annotation: the text renders, but it is not clickable. Nothing is printed on stderr, and the exit code is 0.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>flex link</title>
  <style>.row { display: flex; gap: 8pt; }</style>
</head>
<body>
  <p>A plain link: <a href="#target">plain</a>.</p>
  <div class="row"><span>01</span><a href="#target">a link that is a flex item</a></div>
  <h2 id="target">Target</h2>
</body>
</html>
```

Rendered with `weasyprint flex.html flex.pdf`, with each link alone in its own file and `/Link` annotations counted with pikepdf: the plain link gets 1 annotation, and the flex-item link gets 0. The same holds with `--pdf-variant pdf/ua-1`, where veraPDF then passes the file because there is no link left to check.

Wrapping the link in an inline element inside the flex item (`<span><a href="#target">…</a></span>`) restores the annotation.

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
