# Runtime Validation Report

**Generated:** 2026-11-20
**Target:** `D:\MYHCL_project`

## Summary

| Step | Status | Exit code | Details |
|---|---|---:|---|
| Startup | PASS | 0 | Django runserver and Vite started; frontend returned HTTP 200, backend Swagger returned HTTP 200, and invalid login returned the expected HTTP 401. |
| PostgreSQL and migration | PASS | 0 | Supabase PostgreSQL connection succeeded; migration `core.0006_auditlog_document_notification` is applied exactly once and all three tables exist. |
| Live API workflows | PASS | 0 | 14 API lists and multi-step workflows ran against PostgreSQL using rollback-only fixtures. |
| Backend suite | PASS | 0 | 42 Django tests passed using local SQLite. |
| Frontend checks | PASS | 0 | Oxlint and Vite production build passed. |
| Browser E2E | PARTIAL | N/A | Live login, navigation, document upload form, notification/audit/report screens worked. Export returned HTTP 200, but the browser tool did not report a download event. |

**Overall:** PARTIAL â€” backend, live database, and build checks passed; the
browser's generated-file download event was not independently observed.

## Environment

- Docker: **UNAVAILABLE** â€” Docker daemon did not respond.
- Node.js: **AVAILABLE** â€” `v22.22.3`.
- Playwright CLI: **UNAVAILABLE** â€” `npx --no-install playwright --version`
  reported that the package was missing and canceled rather than installing
  it. No project dependency was added.
- Browser tier: integrated browser/Playwright tools were used against the
  running React app.
- Database tier: the actual configured PostgreSQL database was used for live
  API probes. The full Django suite used SQLite as required.

## Live PostgreSQL Evidence

- `SELECT 1` succeeded and Django identified the connection as PostgreSQL.
- Migration `core.0006_auditlog_document_notification` appears once in
  `django_migrations`; the `core_auditlog`, `core_document`, and
  `core_notification` tables exist.
- The final counts match the pre-verification counts: 2 users, 1 contract,
  0 requisitions, 1 vendor, 2 invoices, 0 purchase orders, 0 documents,
  0 notifications, and 0 audit logs.
- API checks covered JWT login/current user, anonymous rejection, requester
  authorization, all 14 list endpoints, quotation and vendor quote creation,
  purchase-order approvals, delivery creation, document upload/download and
  cross-vendor denial, notification creation/read, audit read-only behavior,
  report filters/CSV, and payment success, expiry, and changed-amount failure.
- All API-created fixtures were rolled back. The temporary browser account and
  its two token rows were removed; no pre-existing business record was deleted
  or updated.

## Browser and Integration Evidence

- Started the frontend at `http://127.0.0.1:5173/` and backend at
  `http://127.0.0.1:8000/`.
- Signed in from the browser using a temporary Contracts Manager account and
  loaded real records from the configured backend.
- Opened the document upload dialog and visited Notifications, Audit History,
  and Reports.
- The UI export action called `/api/reports/export/?report=summary`; the
  backend returned HTTP 200 and `text/csv`. The browser automation timed out
  waiting for a download event, so the file-save behavior remains unverified
  in the browser.
- The generated OpenAPI schema and Swagger UI returned HTTP 200. Schema
  generation logged non-fatal warnings for the current-user and report views;
  live runtime endpoints passed.

## Commands Run

```powershell
cd D:\MYHCL_project\backend
python manage.py runserver 127.0.0.1:8000

cd D:\MYHCL_project\frontend
npm run dev -- --host 127.0.0.1

cd D:\MYHCL_project\backend
$env:DJANGO_USE_SQLITE = "true"
python manage.py test
Remove-Item Env:DJANGO_USE_SQLITE

Set-Location D:\MYHCL_project\frontend
npm run lint
npm run build
```

## Remaining Limitations

- Document files use the local filesystem at `backend/private_documents`, not
  Supabase Storage. Durable storage requires a private persistent volume.
- Contract-expiration notifications require a scheduler to invoke the
  management command daily; email delivery is not configured.
- The browser download event and persistent-file behavior were not verified.
- Excel/PDF exports and deployment configuration are not provided.
- OpenAPI schema warnings remain for the current-user and report views.
