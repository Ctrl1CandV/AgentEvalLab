# Configuration

Each service has config/base.toml and one file per environment (prod.toml, staging.toml).
An environment file may include a shared file with a line include = "<path>", and a shared file may include
another shared file in the same way.
For an environment, a key set in that environment's file itself wins; otherwise a key set in the file it
includes, then in the file that one includes, and so on; otherwise the key's value in base.toml.
The key tier is the service's tier (1, 2 or 3), and upstream names the service that a service sends its
requests to. Both follow the same rules as every other key.
Files ending in .bak are retired copies and are never loaded.

## History

Every change to a prod.toml is recorded in changes/ with its time in UTC, the key, and its value before (From)
and after (To). "(not set)" means that the file did not set the key. Nothing else has changed since
2026-08-31: not base.toml, staging.toml or the shared files, and no include line.
To find a value at a past moment, take each prod.toml as it stood then, by undoing every change recorded after
that moment, and apply the precedence above.
