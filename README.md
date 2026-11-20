# ContractCommand

Defense contract and procurement management platform.

ContractCommand supports contract lifecycle management and a procurement
workflow spanning requisitions, quotation requests, vendor quotes, purchase
orders, approvals, deliveries, and invoices.

## Backend

```powershell
python -m pip install -r requirements.txt
cd D:\MYHCL_project\backend
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### Supabase PostgreSQL

1. Copy the root `.env.example` to `.env`.
2. In Supabase, open **Connect** and copy a PostgreSQL connection URI. Prefer the
   session pooler for app access if a direct database connection is unavailable.
3. Replace the example `DATABASE_URL` in `.env`; URL-encode special characters
   in the password. Keep `.env` local and never commit or share it.
4. From `backend`, run `python manage.py migrate` to create the schema in Supabase.

With `DATABASE_URL` unset, Django continues to use the local SQLite database.
Setting it selects PostgreSQL and requires SSL. Existing SQLite records are not
copied automatically.

To run tests against a temporary local SQLite test database while keeping
Supabase configured in `.env`, use:

```powershell
cd D:\MYHCL_project\backend
$env:DJANGO_USE_SQLITE = "true"
python manage.py test
Remove-Item Env:DJANGO_USE_SQLITE
```

API documentation: `http://127.0.0.1:8000/api/docs/`
Opening the backend root (`http://127.0.0.1:8000/`) redirects to the frontend.
Set `FRONTEND_URL` in the environment when deploying to another frontend URL.

## Authentication and roles

The React app signs in with JWT access and refresh tokens. Access tokens last
15 minutes; refresh tokens last one day and are kept in the current browser
session. Signing out revokes the refresh token. Module APIs require an
authenticated account assigned to one of seven application roles:

| Role | API access |
| --- | --- |
| Contracts Manager | Read/create/update contracts, requisitions, vendors, invoices, quotation requests, purchase orders, and deliveries; read quotes and approvals |
| Safety Officer | Read contracts, invoices, quotation requests, quotes, purchase orders, and deliveries; manage requisitions and vendors |
| Procurement Officer | Read contracts and invoices; manage requisitions, vendors, quotation requests, purchase orders, and deliveries; read quotes and approvals |
| Requester | Read contracts and manage only their own requisitions |
| Approver | Read contracts, requisitions, vendors, invoices, purchase orders, and approvals; decide only assigned purchase-order approvals |
| Finance Officer | Read contracts, requisitions, vendors, purchase orders, approvals, and deliveries; read/update invoices and manage demo payment sessions |
| Vendor | Read only their linked vendor profile, invited quotation requests, own quotes, purchase orders, deliveries, and invoices |

Deleting records is restricted to Django staff/superuser accounts. To enable
vendor access, link the vendor's login account to its vendor record in Django
Admin; existing vendor records are not linked automatically. Django Admin
continues to use Django sessions.

Create an administrator from the `backend` directory with
`python manage.py createsuperuser`. Use `/admin/` to create users and assign
their application group. To reset the migrated demo manager password, run
`python manage.py changepassword demo-manager`. Do not reuse the sample/demo
password for real deployments.

## Frontend

```powershell
cd D:\MYHCL_project\frontend
npm run dev -- --host 127.0.0.1
```

## API

- Sign in: `POST /api/auth/token/`
- Refresh access token: `POST /api/auth/token/refresh/`
- Sign out and revoke refresh token: `POST /api/auth/token/blacklist/`
- Current user: `GET /api/auth/me/`
- Contracts: `/api/contracts/`
- Requisitions: `/api/requisitions/`
- Vendors: `/api/vendors/`
- Invoices: `/api/invoices/`
- Quotation requests: `/api/quotation-requests/`
- Vendor quotes: `/api/vendor-quotes/`
- Purchase orders: `/api/purchase-orders/`
- Purchase-order approval assignments: `/api/approvals/`
- Deliveries: `/api/deliveries/`
- Demo payment sessions: `/api/payment-sessions/`
- Submit a draft purchase order: `POST /api/purchase-orders/{id}/submit/`
- Decide an assigned approval: `POST /api/approvals/{id}/decide/`
- Complete a demo payment: `POST /api/payment-sessions/{id}/complete/`
- List/upload documents: `GET/POST /api/documents/`
- Download a protected document: `GET /api/documents/{id}/download/`
- List notifications and mark one read: `GET /api/notifications/`, `PATCH /api/notifications/{id}/mark-read/`
- Read authorized audit history: `GET /api/audit-logs/`
- Read filtered reports: `GET /api/reports/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&status=PAID`
- Export a report as CSV: `GET /api/reports/export/?report=summary`
- Swagger: `/api/docs/`

Demo payment sessions can be created by Finance Officers for approved invoices.
They expire ten minutes after creation; completing one marks the invoice paid.
This is a local workflow simulation and does not connect to a payment provider
or collect payment credentials.

## Documents, notifications, audit, and reports

Documents can be attached to contracts, quotation requests or vendor quotes,
purchase orders, invoices, and deliveries. Uploads accept PDF, DOCX, XLSX, PNG,
JPG, and UTF-8 TXT files up to 10 MB. The API validates the filename extension,
reported content type, and file signature where supported. Files are stored
outside Django's public media URL and downloads require authentication and
record-level access. Storage currently uses the local filesystem, not Supabase
Storage. The default private directory is `backend/private_documents`; files
persist only as long as that host filesystem does. Set `PRIVATE_DOCUMENT_ROOT`
to a private, persistent mounted directory in deployments. Do not mount it as
a static or public media directory.

Notifications are in-app and scoped to the signed-in user. Requisition
decisions, invoice submissions and payment updates, pending purchase-order
approvals, approval outcomes, and contract-expiration reminders create
notifications. Marking a notification read only changes its read timestamp.
Contract reminders are idempotent and can be run daily by a scheduler:

```powershell
cd D:\MYHCL_project\backend
python manage.py send_contract_expiration_notifications
```

The command defaults to active contracts expiring within 30 days. Use
`--days 14` to change the window. No email or external notification provider is
configured.

The audit API is read-only. Contracts Managers and Finance Officers can view
audit history; platform staff can also view it through the API and Django
Admin. The frontend provides an audit history view and a reports dashboard.
Reports include procurement expenditure, contract status, vendor performance,
invoice/payment status, and requisition statistics. Date and status filters
apply to the report data. CSV exports support `summary`, `expenditure`,
`contracts`, `vendors`, `invoices`, `payments`, and `requisitions`; Excel and
PDF exports are not currently provided.

The feature schema is in additive migration
`core.0006_auditlog_document_notification`. It has been applied to the
configured Supabase database; the existing user, contract, requisition, vendor,
and invoice counts were unchanged. Run `python manage.py migrate` when
deploying to another environment. The migration creates new tables and does
not reset or delete existing records.

## Final verification

The configured Supabase PostgreSQL connection was verified with a live query.
Migration `core.0006_auditlog_document_notification` is recorded exactly once,
and its three tables exist. Final existing counts are 2 users, 1 contract,
0 requisitions, 1 vendor, and 2 invoices. All 14 API list endpoints and the
authentication, role-permission, procurement, document, notification, audit,
report, and payment workflows were exercised against PostgreSQL using
rollback-only fixtures; the counts remained unchanged.

The complete Django suite passes **42 tests** using local SQLite. Django checks
and migration consistency checks pass. Frontend lint and production build pass.
The browser loaded the React app, signed in against the configured backend,
and opened the document, notification, audit, and report screens. The report
export request returned HTTP 200; the browser automation did not capture the
resulting file-download event.

The current deployment is not fully configured: document storage needs a
persistent private volume, the reminder command needs a daily scheduler, and
email plus Excel/PDF exports are not configured. See
[DEVELOPMENT_PROGRESS.md](./DEVELOPMENT_PROGRESS.md) for the detailed
verification record and
[runtime validation report](./docs/runtime-validation-report.md) for test
evidence and remaining limitations.

## Release

The initial `v1.0.0` release included the original four core modules:

- Contract lifecycle management
- Procurement requisitions
- Vendor evaluation
- Invoice management

The current working tree adds quotation, purchase-order approval, delivery,
demo-payment, document, notification, audit, and reporting workflows.

See [DEVELOPMENT_PROGRESS.md](./DEVELOPMENT_PROGRESS.md) for verified progress
and remaining scope, and [database/ERD.md](./database/ERD.md) for the current
data model diagram.
