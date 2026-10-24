# Configuration

Each service has config/base.toml and one file per environment (prod.toml, staging.toml).
An environment file may include a shared file with a line include = "<path>", and a shared file may include
another shared file in the same way.
For an environment, a key set in that environment's file itself wins; otherwise a key set in the file it
includes, then in the file that one includes, and so on; otherwise the key's value in base.toml.
Files ending in .bak are retired copies and are never loaded.

Every production change is recorded in changes/ with its date, the key, and its value before and after.
A change takes effect on its date: the value at the end of a day is the value after that day's changes.
A prod.toml may name the service it sends requests to with a line upstream = "<service>".
