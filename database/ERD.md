# ContractCommand entity relationship diagram

```mermaid
erDiagram
    USER {
        bigint id PK
        string username
    }

    CONTRACT {
        bigint id PK
        string contract_number UK
        string status
        decimal value
        bigint owner_id FK
    }

    REQUISITION {
        bigint id PK
        string requisition_number UK
        string status
        decimal estimated_value
        bigint requested_by_id FK
        bigint contract_id FK
    }

    VENDOR {
        bigint id PK
        string registration_number UK
        string name
        boolean approved
        bigint user_id FK
    }

    INVOICE {
        bigint id PK
        string invoice_number UK
        string status
        decimal amount
        bigint vendor_id FK
        bigint contract_id FK
        bigint purchase_order_id FK
    }

    QUOTATION_REQUEST {
        bigint id PK
        string request_number UK
        string status
        bigint requisition_id FK
        bigint created_by_id FK
    }

    VENDOR_QUOTE {
        bigint id PK
        decimal amount
        string status
        bigint quotation_request_id FK
        bigint vendor_id FK
    }

    PURCHASE_ORDER {
        bigint id PK
        string po_number UK
        string status
        decimal amount
        bigint requisition_id FK
        bigint vendor_id FK
        bigint quote_id FK
        bigint contract_id FK
        bigint created_by_id FK
    }

    APPROVAL {
        bigint id PK
        string status
        bigint purchase_order_id FK
        bigint approver_id FK
    }

    DELIVERY {
        bigint id PK
        string delivery_number UK
        string status
        bigint purchase_order_id FK
        bigint created_by_id FK
    }

    PAYMENT_SESSION {
        bigint id PK
        string session_id UK
        decimal amount
        string status
        datetime expires_at
        bigint invoice_id FK
        bigint created_by_id FK
    }

    DOCUMENT {
        bigint id PK
        string document_type
        string original_filename
        string content_type
        bigint size_bytes
        bigint contract_id FK
        bigint quotation_request_id FK
        bigint vendor_quote_id FK
        bigint purchase_order_id FK
        bigint invoice_id FK
        bigint delivery_id FK
        bigint uploaded_by_id FK
    }

    NOTIFICATION {
        bigint id PK
        string notification_type
        string message
        string related_type
        string related_id
        datetime created_at
        datetime read_at
        bigint user_id FK
    }

    AUDIT_LOG {
        bigint id PK
        string action
        string entity_type
        string object_id
        string object_label
        json changes
        string ip_address
        datetime created_at
        bigint user_id FK
    }

    USER ||--o{ CONTRACT : owns
    USER ||--o{ REQUISITION : requests
    USER ||--o| VENDOR : "linked account"
    USER ||--o{ QUOTATION_REQUEST : creates
    USER ||--o{ PURCHASE_ORDER : creates
    USER ||--o{ APPROVAL : decides
    USER ||--o{ DELIVERY : records
    USER ||--o{ PAYMENT_SESSION : creates
    USER ||--o{ DOCUMENT : uploads
    USER ||--o{ NOTIFICATION : receives
    USER o|--o{ AUDIT_LOG : performs

    CONTRACT o|--o{ REQUISITION : supports
    CONTRACT ||--o{ INVOICE : governs
    CONTRACT o|--o{ PURCHASE_ORDER : references

    REQUISITION ||--o{ QUOTATION_REQUEST : requests
    REQUISITION ||--o{ PURCHASE_ORDER : authorizes
    VENDOR }o--o{ QUOTATION_REQUEST : invited
    QUOTATION_REQUEST ||--o{ VENDOR_QUOTE : receives
    VENDOR ||--o{ VENDOR_QUOTE : submits
    VENDOR ||--o{ PURCHASE_ORDER : fulfills
    VENDOR ||--o{ INVOICE : bills
    VENDOR_QUOTE o|--o{ PURCHASE_ORDER : selected_for

    PURCHASE_ORDER ||--o{ APPROVAL : requires
    PURCHASE_ORDER ||--o{ DELIVERY : receives
    PURCHASE_ORDER o|--o{ INVOICE : billed_by
    INVOICE ||--o{ PAYMENT_SESSION : paid_through
    CONTRACT o|--o{ DOCUMENT : contains
    QUOTATION_REQUEST o|--o{ DOCUMENT : contains
    VENDOR_QUOTE o|--o{ DOCUMENT : contains
    PURCHASE_ORDER o|--o{ DOCUMENT : contains
    INVOICE o|--o{ DOCUMENT : contains
    DELIVERY o|--o{ DOCUMENT : contains
```

`USER` represents Django's configured user model. `VENDOR.user_id` is nullable
and one-to-one. `INVOICE.purchase_order_id`, `PURCHASE_ORDER.quote_id`, and
`PURCHASE_ORDER.contract_id` are nullable. Each approval is unique per
purchase-order/approver pair, and each vendor may submit at most one quote per
quotation request. A document must reference exactly one supported business
record; its file is stored in private filesystem storage and downloaded only
through the authorized API. Audit-log entity references are descriptive rather
than foreign keys so history remains after business records are deleted.
