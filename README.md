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

## Print Formats

`Reytinas Devis` and `Reytinas Facture` are seeded once on app install if they do not exist.

After that, edit them directly in ERPNext:

- go to `Print Format`
- open `Reytinas Devis` or `Reytinas Facture`
- edit HTML/CSS in Desk
- save and test from the document print preview

`bench migrate` does **not** overwrite existing print formats anymore.

To export a validated version from the database:

```bash
docker exec erpnext-backend-1 bench --site comptabilite.reytinas.fr execute \
  reytinas_erpnext.print_formats.export_print_formats \
  --kwargs "{'output_path': '/tmp/reytinas-print-formats.json'}"
docker cp erpnext-backend-1:/tmp/reytinas-print-formats.json /srv/git/quentinreytinas/reytinas_erpnext/reytinas-print-formats.json
```

To force-reapply the app template to the database once:

```bash
docker exec erpnext-backend-1 bench --site comptabilite.reytinas.fr execute \
  reytinas_erpnext.print_formats.sync_print_formats \
  --kwargs "{'force': 1}"
```
