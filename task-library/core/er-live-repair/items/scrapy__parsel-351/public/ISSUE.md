Warn on XPath expression starting with `/` on a non-root selector

A relatively common issue Scrapy users face when using Scrapy and XPath expressions for the first time, and one that still can hit Scrapy experts now and then, is to use `//` instead of `.//` on nested selectors, which causes the expression to apply to the entire document instead of the subset of the document in the nested selector.

For example:

```python
for h1 in response.xpath("//h1"):
    if h1.xpath("//span"): ...
```

That second XPath expression was probably meant to be `.//span` instead.

[I was hoping to implement this kind of check in a static analysis tool](https://github.com/scrapy/scrapy/issues/4421#issuecomment-629129705), but I see no reliable way to implement it on top of the AST.

I wonder if it would make sense to implement a run-time warning in parsel: if `xpath` is used on a non-root selector, and the expression starts with `/`, warn about it.

My main concern here is:
- Are there valid use cases for this? (the example in my next point kind of answers “Yes” to this point)
- Is it OK that users need to use the standard Python API to silence such warning if they hit a case where they actually want this? (e.g. maybe they are passing a nested selector around to some functions but not the root selector, and they prefer to use the nested selector as a proxy to the root selector instead of passing the root selector to the function as well)
