# ContractCommand

Defense contract and procurement management platform.

ContractCommand supports contract lifecycle management, procurement
requisitions, vendor evaluation, and invoice/payment processing.

## Backend

```powershell
cd backend
python manage.py migrate
python manage.py runserver
```

API documentation: `http://127.0.0.1:8000/api/docs/`

## Frontend

```powershell
cd frontend
npm run dev
```

## API

- Contracts: `/api/contracts/`
- Requisitions: `/api/requisitions/`
- Vendors: `/api/vendors/`
- Invoices: `/api/invoices/`
- Swagger: `/api/docs/`

## Release

The `v1.0.0` release includes all four core modules:

- Contract lifecycle management
- Procurement requisitions
- Vendor evaluation
- Invoice and payment processing
