# Candidate Task Card: eng-003 Local Resource Manager

## Identity and scope

- ID: `eng-003-resource-manager`
- Family: `eng-stateful-interactive`
- Status: screening; functional calibration recorded; not frozen
- Primary capability: stateful engineering with persistence, forms, import/export, and recovery

## User goal

Implement a local resource-management application from an empty workspace: a Python service layer, a standard-library HTTP server, a small browser frontend, and a README.

## Fixed contract

The package instruction fixes the data model, `ResourceStore` API, validation rules, atomic persistence and corrupt-file recovery, import merge/replace behavior, all-or-nothing imports, HTTP routes and status codes, and form states. Internal organization and frontend implementation are flexible.

## Evidence and limits

The functional layer has offline reference and mutation calibration, including CRUD, validation, persistence, recovery, and import/export. Visual review and real-model runs remain pending. The task uses synthetic data and does not test deployment, authentication, multiple users, or production scale.
