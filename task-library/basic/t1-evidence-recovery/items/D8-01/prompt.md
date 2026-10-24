## Snapshot D8-01

The read-only snapshot holds the fictional project quiet-ledger. Answer these questions:

- Q1: Incident INC-989 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream twice. What is the effective production queue_depth of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q2: Incident INC-639 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream twice. What is the effective production pool_size of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q3: Incident INC-237 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream once. What is the effective production timeout_ms of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q4: Incident INC-622 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream twice. What is the effective production max_retries of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q5: Incident INC-289 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream three times. What is the effective production timeout_ms of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.

Emit one JSON object only, without Markdown fences, with one key per question: {"Q1": {...}, "Q2": {...}, "Q3": {...}, "Q4": {...}, "Q5": {...}}.
