`tox.toml` posargs Tox variable substitution.

## What's the problem this feature will solve?

With `tox.ini` being deprecated we are migrating over to `tox.toml`.
In our implementation we pass arguments to a pytest command run by tox via posargs and we rely on the Tox var substitution in order to name the output of certain generated files e.g. set the name of an output file based off of the tox environment the command ran within . 

## Describe the solution you'd like

 Adding support for substitution on toml posargs gated on a flag would be suitable, this would retain preexisting behavior but enable feature parity with the `tox.ini`, it could be implemented similarly to the extend flag that already exists. e.g.
```
{replace = "posargs", default = ["tests"], extend = true, substitute = true }
```

Usecase:
Scenario, command specified within `tox.toml` as defined below, substitute flag enabled,
```
commands = [
  ["pytest", {replace = "posargs", extend = true, substitute = true}]
]
```

A script optionally generates per-environment reports in a given location by running tox like so 
`tox -- --extra-arg=a_dir/{env_name}.blah`.

In the current `tox.toml` implementation these values would be literal and it would run `pytest --extra-arg=a_dir/{env_name}.blah` , in the implemented version it may run `pytest --extra-arg=a_dir/314-linux.blah`.

## Alternative Solutions

Attempted 3 workarounds within Tox:

1) Specific to pytest, used its PYTEST_ADDOPTS envvar to pass in args, as substitutions are performed within read in values. I did not like this approach as it blocks off our users from using this handle.

2) Conditional blocks specified within the toml, like
```
commands = [
  ["pytest", {replace = "if", condition = "env.FLAG_ENVVAR == 1", then = ["--extra-arg=a_dir/{env_name}.blah"], else = [], extend = true}]
]
``` 
where setting FLAG_ENVVAR to a certain value enables the feature.
I don't like this approach because it requires me to update the `tox.toml` if this command interface ever changes or if I want to add anything else in the future I'm again going to have to edit the toml itself.
I would prefer not having to have the `tox.toml` need knowledge of these possible options that a wrapper script might want pass.

3) Via Override. An empty placeholder var is set within the `tox.toml` I then append this to the end of the pytest command like posargs. Then when the script calls tox I use the `-x` arg to override the value of the placeholder var. Substitutions are performed as expected within overrides so this behaves like the rest.
