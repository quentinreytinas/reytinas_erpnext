# reytinas_erpnext

This is the placeholder for the Reytinas custom ERPNext app.

Use this app for:

- supported hooks and boot/session behavior
- fixtures and custom DocTypes
- reports, pages, workspaces, and API glue
- migration of local business logic that must not live in `frappe` or `erpnext`

Do not use it for:

- patching `frappe` or `erpnext` source files
- patching third-party apps directly in production containers

Before using it in image builds, extract it into its own Git repository and reference that repository from `deployments/reytinas/apps.reytinas.example.json`.
