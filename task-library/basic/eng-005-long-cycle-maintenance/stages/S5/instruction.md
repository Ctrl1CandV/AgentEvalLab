# S5: Error Protocol and Final Delivery

Complete cleanup and check behavior across the project. Every failed command must emit one JSON line to stdout:
{"ok":false,"error":{"code":"...","message":"..."}}
and exit with code 2 without a stack trace. Successful output keeps its existing JSON or CSV shape.

Stable error codes must include INVALID_ARGUMENT, NOT_FOUND, DUPLICATE_ID, INVALID_STATUS_TRANSITION, SELF_DEPENDENCY, DEPENDENCY_CYCLE, DEPENDENCY_NOT_COMPLETE, STORE_INVALID, and UNKNOWN_COMMAND. Repeated occurrences of the same error class must use the same code.

Update README to accurately document commands, pagination defaults, dependency rules, the error protocol, automatic v1-to-v2 migration, and event fields. Run all stage regressions. Preserve source files, v2 state, event history, and existing work orders. Do not remove or weaken checkers, fixtures, self-tests, or data to pass.
