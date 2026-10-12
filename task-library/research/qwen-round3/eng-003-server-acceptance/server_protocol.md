# eng-003 Submitted-Server Acceptance Protocol

The prototype checks three dimensions separately: importing the submitted service module, starting the submitted server and exercising HTTP behavior, and browser UI review.

## HTTP procedure

Start the submitted server on an available local port, poll a readiness endpoint, issue CRUD and import/export requests, then terminate and reap the process. A successful cleanup requires the process to exit and the port to be reusable. Use bounded waits and avoid confusing TIME_WAIT with a live listener.

## Historical self-calibration

The good submission passed the store and HTTP checks and was cleaned up. A valid store with no server passed the store checks but failed HTTP acceptance. A server with a missing POST route returned 404 and was rejected. Browser UI evaluation remained blocked because no rendering backend was available.

## Limits

This is an offline prototype, not a real-model result or OS security boundary. Keep the submitted server in a temporary isolated directory and use an outer timeout. See acceptance_prototype.py and the associated log for the historical run.
