# eng-003 Runtime and Execution Plan

The task uses Python 3.13 standard library only. Persist data to a local JSON file; do not use a database service or network dependency.

The candidate receives instruction.md and public/ and builds service.py, server.py, and frontend/. The evaluator imports the submitted service module for headless checks, starts the submitted server for HTTP checks, and checks the frontend package. Private references, flawed examples, and acceptance code remain under private/.

Historical offline calibration passed 14/14 functional checks plus a small HTTP smoke test. This does not validate visual quality. Browser rendering, full responsive checks, and full accessibility scans require a rendering backend and remain blocked. No real model API or budget experiment has been used.
