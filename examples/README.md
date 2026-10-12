# Example Plans

These plans demonstrate the evaluation schema and task-package pins. They are examples for validation and review; they do not authorize a live model run.

Use `--validate-only` to check a plan without loading credentials or sending requests:

```powershell
npm run harness -- --plan examples/eng-001.eval.json --validate-only
```

Before a live run, review the model selection, task versions, tool profile, request budget, timeout, output limits, and cost ceiling.
