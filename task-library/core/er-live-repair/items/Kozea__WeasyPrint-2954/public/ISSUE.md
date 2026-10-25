Grid rows sized `minmax(<length>, auto)` don't grow to fit their content

When a grid row has a fixed minimum and a content-based maximum, for example `minmax(20px, auto)`,
WeasyPrint keeps the row at its minimum size, even when the content is taller. The content then
overflows onto the next row. Browsers grow the row to fit its content.

```html
<style>
  .grid {
    display: grid;
    grid-template-columns: 200px;
    grid-auto-rows: minmax(20px, auto);
  }
  .grid div { border: 2px solid }
</style>
<div class="grid">
  <div style="background: #fcc">Line 1<br>Line 2<br>Line 3</div>
  <div style="background: #ccf">Next row</div>
</div>
```

| Chrome | WeasyPrint 70.0 |
|---|---|
| <img width="300" alt="Chrome" src="https://github.com/user-attachments/assets/a75a8606-cf45-4ad6-9715-467d43dbcdd4" /> | <img width="300" alt="WeasyPrint" src="https://github.com/user-attachments/assets/168bdd78-12be-4f13-b5e4-f9ce7fa4bd5b" /> |


The same thing happens with `minmax(<length>, max-content)`. With `minmax(0, auto)`, the row collapses to 0.

I think the cause is in `layout/grid.py`. When sizing tracks for non-spanning items in the block
direction, the keyword check is `'max_content'` instead of `'max-content'`, and `auto` is missing from
the check on the max function. So these rows' growth limits are never set from their content. Also,
the "Maximize tracks" step is skipped when the grid's height is `auto`.

This seems related to "distribute space beyond limits" in #2145: once the growth limits are fixed,
spanning items need that step too.

I'd be happy to work on a fix if that's OK with you.
