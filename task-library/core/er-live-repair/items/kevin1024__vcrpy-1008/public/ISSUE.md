Incorrect error mesage when loading python objects

Hi, after the change to use a safe YAML loader: https://github.com/kevin1024/vcrpy/commit/045acb1b5f8940f82adbb3faafd13e43e46289d6 ,if we try to load a casette that have a tag `tag:yaml.org,2002:python/object/new` it's raising an error: "Your cassette files were generated in an older version of VCR", even if we re-create the casettes with 8.2.1.  Probably the easiest change is to change that error message, for a more generic "There was a problem loading the casette".
Is there a way to allow custom python constructors, without using private methods? Something like this works if anyone is having the same problem:
```
yamlserializer._CassetteLoader.add_constructor(
    "tag:yaml.org,2002:python/object/new:some.route",
    some_converter_function,
)
```
