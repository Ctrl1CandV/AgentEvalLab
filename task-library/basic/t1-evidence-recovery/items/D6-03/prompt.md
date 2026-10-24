## Snapshot D6-03

The read-only snapshot holds the fictional project quiet-harvest. Answer these questions:

- Q1: Incident INC-540 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream twice. What is the effective production batch_size of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q2: Incident INC-280 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream three times. What is the effective production timeout_ms of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q3: Incident INC-174 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream twice. What is the effective production queue_depth of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q4: Incident INC-524 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream three times. What is the effective production max_retries of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q5: Incident INC-568 was caused by a configuration change. Start from the service whose configuration that change set and follow its production upstream once. What is the effective production cache_ttl_s of the service you reach? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.

Emit one JSON object only, without Markdown fences, with one key per question: {"Q1": {...}, "Q2": {...}, "Q3": {...}, "Q4": {...}, "Q5": {...}}.
