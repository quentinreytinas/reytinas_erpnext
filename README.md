# reytinas_erpnext

This is the placeholder for the Reytinas custom ERPNext app.

Use this app for:

- supported hooks and boot/session behavior
- fixtures and custom DocTypes
- naming series and document naming hooks
- reports, pages, workspaces, and API glue
- migration of local business logic that must not live in `frappe` or `erpnext`

Naming series property setters for quotes and invoices are synchronized on app install
and on `bench migrate`.

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

## EnableBanking

The app includes an EnableBanking integration scaffold for importing bank transactions
into ERPNext `Bank Transaction`.

Main pieces:

- `EnableBanking Settings` single DocType for API credentials and callback URL
- `EnableBanking Account Link` DocType to bind one ERPNext `Bank Account` to one
  authorized EnableBanking account
- whitelisted methods in `reytinas_erpnext.enablebanking.api`
- scheduled sync in `reytinas_erpnext.enablebanking.sync`

Suggested rollout:

1. `bench migrate` to create the new DocTypes.
2. Open `EnableBanking Settings` and fill in the API base URL, Application ID,
   Key ID, and PEM private key.
3. Call `reytinas_erpnext.enablebanking.api.get_aspsps` to list supported banks.
4. Call `reytinas_erpnext.enablebanking.api.start_authorization` for a `Bank Account`.
5. Complete the bank authorization flow and let the callback import transactions.
