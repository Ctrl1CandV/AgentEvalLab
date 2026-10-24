# Configuration

Each service has config/base.toml and one file per environment (prod.toml, staging.toml).
For an environment, a key set in that environment's file overrides the same key in base.toml.
A key not set in the environment file takes its value from base.toml.
Files ending in .bak are retired copies and are never loaded.
