Optional inner validators for `deep_mapping`
This is a copy of the fourth issue collected in https://github.com/python-attrs/attrs/issues/1206 to enable separate tracking of the bug.

### The issue
For `deep_iterable`, only the `iterable_validator` is optional, which makes sense because if no `member_validator` was provided, one should simply use a regular validator in the first place. However, for `deep_mapping`, both `value_validator` and `key_validator` are required. This makes its use unnecessarily complicated in certain situations. For example, validating only dictionary keys requires a rather cumbersome workaround and also results in unnecessary calls of the `value_validator`:
```python
@define
class B:
    x: Dict[str, Any] = field(
        validator=deep_mapping(
            key_validator=and_(instance_of(str), min_len(1)),
            value_validator=lambda *x: None,
        )
    )
```
Instead, I guess the user-friendly way would be to check that **at least one of them** is provided, but not necessarily both.
