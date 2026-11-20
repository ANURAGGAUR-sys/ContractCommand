# Development progress

## Completed

- Replaced API session authentication with JWT access/refresh tokens while
  retaining Django sessions for Admin.
- Added seven application roles, role-based module capabilities, requester
  requisition ownership, vendor record scoping, and assigned-approver checks.
- Added quotation requests, vendor quotes, purchase orders, multi-approver
  decisions, delivery tracking, and demo payments.
- Added private document upload and protected download for contracts,
  quotations, purchase orders, invoices, and delivery receipts, with file
  type/signature checks and a 10 MB limit.
- Added user-scoped in-app notifications for requisition decisions, invoice
  submission and payment, pending approvals, and approval outcomes. Added an
  idempotent management command for contract-expiration reminders.
- Added immutable audit records and an authorized audit-history view.
- Added date/status-filtered procurement, contract, vendor, invoice/payment,
  and requisition reports with CSV export.
- Integrated document, notification, audit, and report screens into the React
  application.
- Added additive migration `core.0006_auditlog_document_notification` and
  applied it to the configured Supabase database.
- Updated API documentation and the entity relationship diagram.

## Final verification — 2026-11-20

- Supabase PostgreSQL connectivity: passed; a live `SELECT 1` succeeded.
- Migration `core.0006_auditlog_document_notification`: applied and recorded
  exactly once; all three new tables exist.
- Final existing counts: 2 users, 1 contract, 0 requisitions, 1 vendor, and
  2 invoices. The document, notification, and audit tables are empty.
- All 14 API list endpoints returned success against PostgreSQL. Rollback-only
  API workflows verified JWT login, anonymous denial, role restrictions,
  requisition/quotation/purchase-order approvals/delivery, document upload and
  authorized download, notification creation/read, immutable audit access,
  filtered reports/CSV, and payment success, amount-mismatch failure, and
  expiry within the 10-minute session window.
- Test fixtures were rolled back; the temporary browser login account and its
  token rows were removed. Final record counts match the pre-test counts.
- Django test suite: **42 tests passed** (exit code 0) using local SQLite.
- Django system and migration consistency checks: passed.
- Frontend lint and production build: passed.
- Frontend/backend browser smoke: login against the configured backend and
  document, notification, audit, and report screens loaded. The report export
  endpoint returned HTTP 200, but the browser harness did not observe the
  generated file-download event.
- `git diff --check`: passed.

The full Django test suite was run with `DJANGO_USE_SQLITE=true`; do not run it
against Supabase. Detailed evidence is in
[runtime-validation-report.md](./docs/runtime-validation-report.md).

## Deployment follow-ups

- Apply the already-tested migration to any other deployment environments.
- File storage currently uses the local filesystem at
  `backend/private_documents`; it is not Supabase Storage and is only
  persistent if the host volume is persistent. Configure `PRIVATE_DOCUMENT_ROOT`
  as private durable storage before deploying uploads.
- Schedule `python manage.py send_contract_expiration_notifications` daily.
  The command creates reminders for active contracts expiring within 30 days
  by default.
- In-app notifications are implemented; email delivery is not configured.
- CSV export is implemented; Excel/PDF export and browser-level end-to-end
  download verification remain incomplete.
- Deployment configuration remains to be added.
- Swagger schema generation returned successfully but logged non-fatal schema
  warnings for the current-user and report views; runtime API checks passed.
