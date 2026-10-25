Content getting duplicated in absolute containers(?)

WeasyPrint 68.1 (actually the current `main` branch as of f14d4f32)
```
System: Linux
Machine: x86_64
Version: #19~24.04.2-Ubuntu SMP PREEMPT_DYNAMIC Fri Mar  6 23:08:46 UTC 2
Release: 6.17.0-19-generic

WeasyPrint version: 68.1
Python version: 3.12.3
Pydyf version: 0.12.1
Pango version: 15201
```

In the following example, the text content on the second page is getting duplicated for no apparent reason. I couldn't find a smaller way to reproduce this, so I'm not sure which parts exactly cause it.

```html
<style>
  @page {
    size: A4;
  }

  .page1-content {
    height: 200mm;
  }

  .page2-content {
    height: 200mm;
    position: relative;
  }

  .inner1 {
    position: absolute;
  }

  .inner2 {
    position: absolute;
    top: 10em;
  }
</style>

<div class="page1-content">
  first page content
</div>

<div class="page2-content">
  <div class="inner1">
    <div class="inner2">
      <br><br>this text is getting duplicated
    </div>
  </div>
</div>
```
