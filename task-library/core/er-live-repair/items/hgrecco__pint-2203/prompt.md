## Issue (hgrecco/pint)

Import from a tuple with invalid units raises no exception
# Versions
* pint [from current master](https://github.com/hgrecco/pint/commit/40034593b803ce4fb48d755d3ac55f14fa8cd1dd)
* python 3.12.2 (can reproduce with 3.11 and 3.10 too)

# Example to reproduce:

```python
In [1]: import pint

In [2]: ureg = pint.UnitRegistry()

In [4]: q1 = ureg.Quantity(1, 'm')

In [5]: q1.to_tuple()
Out[5]: (1, (('meter', 1),))

In [6]: q1 = ureg.Quantity.from_tuple((1, (('meter', 1),)))

In [7]: q1.dimensionality
Out[7]: <UnitsContainer({'[length]': 1})>

In [8]: q2 = ureg.Quantity.from_tuple((1, (('wrong', 1),)))

In [9]: q2.dimensionality
---------------------------------------------------------------------------
AttributeError                            Traceback (most recent call last)
File /lib/python3.12/site-packages/pint/facets/numpy/quantity.py:248, in NumpyQuantity.__getattr__(self, item)
    247 try:
--> 248     return getattr(self._magnitude, item)
    249 except AttributeError:

AttributeError: 'int' object has no attribute 'dimensionality'

During handling of the above exception, another exception occurred:

AttributeError                            Traceback (most recent call last)
Cell In[9], line 1
----> 1 q2.dimensionality

File /lib/python3.12/site-packages/pint/facets/numpy/quantity.py:250, in NumpyQuantity.__getattr__(self, item)
    248     return getattr(self._magnitude, item)
    249 except AttributeError:
--> 250     raise AttributeError(
    251         "Neither Quantity object nor its magnitude ({}) "
    252         "has attribute '{}'".format(self._magnitude, item)
    253     )

AttributeError: Neither Quantity object nor its magnitude (1) has attribute 'dimensionality'
```

# Observed behavior

The line  `q2 = ureg.Quantity.from_tuple((1, (('wrong', 1),)))` does not raise any exception and creates a Quantity object. The object is not usable, e.g. `q2.dimensionality` raises an exception. In addition, any operation on the object raises an exception.

# Expected behavior

With the line `q2 = ureg.Quantity.from_tuple((1, (('wrong', 1),)))` pint should raise this exception:

```python
UndefinedUnitError: 'wrong' is not defined in the unit registry
```

as with the line

```python
q2 = ureg.Quantity(1, 'wrong')
```

# Workaround

The user can add this line (or similar) before loading from the tuple:

```python
ureg.get_name('wrong')
```

to get the exception.

# Solution

not known

The repository is in `repo/`; this issue is also in `public/ISSUE.md`.
