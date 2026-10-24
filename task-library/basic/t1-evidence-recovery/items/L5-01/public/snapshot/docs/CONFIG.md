# Configuration

Each service has config/base.toml and one file per environment (prod.toml, staging.toml).
An environment file may include a shared file with a line include = "<path>".
For an environment, a key set in that environment's file itself wins; otherwise a key set in the file it
includes; otherwise the key's value in base.toml.
Files ending in .bak are retired copies and are never loaded.
