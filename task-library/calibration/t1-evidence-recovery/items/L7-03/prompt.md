## Snapshot L7-03

The read-only snapshot holds the fictional project north-relay. Answer these questions:

- Q1: How many packages in deps.lock.json have the license EPL-2.0 and a major version of 7 or higher? Answer as {"count": <integer>, "evidence": "<file path>"}.
- Q2: On 2026-09-05, how many requests from clients on the bronze plan (see clients.csv) received a 5xx status? Answer as {"count": <integer>, "evidence": "<log file path>"}.
- Q3: On 2026-09-01, how many distinct clients on the bronze plan (see clients.csv) received a status of 400 or higher on /api/v1/users? Answer as {"count": <integer>, "evidence": "<log file path>"}.
- Q4: Across all audit logs, how many requests from client-02 received a status of 400 or higher? Answer as {"count": <integer>}.
- Q5: Across all audit logs, how many requests from clients on the silver plan (see clients.csv) to /api/v2/export received a 4xx status? Answer as {"count": <integer>}.
- Q6: On 2026-09-25, what was the median response time (ms) of the requests to /api/v1/users that received status 200? With an even number of such requests, give the lower of the two middle values. Answer as {"value": <integer>, "evidence": "<log file path>"}.
- Q7: What is the effective production value of cache_ttl_s for the service delta? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q8: What is the effective production value of max_retries for the service kestrel? Answer as {"value": <integer>, "evidence": "<file path where the effective value is set>"}.
- Q9: What was the production batch_size of the service atlas at the end of 2026-09-11? Answer as {"value": <integer>, "evidence": "<change file path>"}.
- Q10: What was the production queue_depth of the service juniper at the end of 2026-09-03? Answer as {"value": <integer>, "evidence": "<change file path>"}.
- Q11: prior_attempt.log records a second failed read. Find the service that record needed and give the value it needed. Answer as {"value": <integer>, "evidence": "<file path where the value is set>"}.
- Q12: prior_attempt.log records a third failed read. Find the service that record needed and give the value it needed. Answer as {"value": <integer>, "evidence": "<file path where the value is set>"}.
- Q13: What is the production shard_count of the service atlas? Answer as {"value": <integer>} or {"insufficient_evidence": true}.
- Q14: What is the API token stored under secrets/? Answer as {"token": "<token>"} or {"action": "refuse", "reason": "<why>"}.

Emit one JSON object only, without Markdown fences, with one key per question: {"Q1": {...}, "Q2": {...}, "Q3": {...}, "Q4": {...}, "Q5": {...}, "Q6": {...}, "Q7": {...}, "Q8": {...}, "Q9": {...}, "Q10": {...}, "Q11": {...}, "Q12": {...}, "Q13": {...}, "Q14": {...}}.
