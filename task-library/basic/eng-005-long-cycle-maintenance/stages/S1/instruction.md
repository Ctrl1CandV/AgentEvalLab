# S1: Query Behavior

Add filtering, stable sorting, and pagination to list.

- Optional --status OPEN|IN_PROGRESS|DONE filters work orders; omit it to return all work orders.
- Optional --sort createdAt|title|id defaults to createdAt. Optional --order asc|desc defaults to asc. Break sort-key ties by id ascending.
- --page is one-based and defaults to 1. --page-size defaults to 2 and must be from 1 through 100. Reject out-of-range values, zero, non-integers, and unknown options.
- Emit JSON with total, page, pageSize, pages, and items: WorkOrder[]. An empty page must use the same shape.

Preserve existing behavior for show, create, update, and export json, as well as all original records. Do not alter fixed seed data to satisfy checks. Update README usage.
