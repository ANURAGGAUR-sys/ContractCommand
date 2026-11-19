CREATE TABLE IF NOT EXISTS core_vendor (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    registration_number VARCHAR(50) NOT NULL UNIQUE,
    contact_email VARCHAR(254) NOT NULL,
    phone VARCHAR(30) NOT NULL DEFAULT '',
    compliance_score SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS core_contract (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    contract_number VARCHAR(30) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    value DECIMAL(14,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    owner_id BIGINT UNSIGNED NOT NULL
);

CREATE TABLE IF NOT EXISTS core_requisition (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    requisition_number VARCHAR(30) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    justification TEXT NOT NULL,
    estimated_value DECIMAL(14,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    requested_by_id BIGINT UNSIGNED NOT NULL,
    contract_id BIGINT UNSIGNED NULL
);

CREATE TABLE IF NOT EXISTS core_invoice (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    invoice_number VARCHAR(30) NOT NULL UNIQUE,
    amount DECIMAL(14,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    vendor_id BIGINT UNSIGNED NOT NULL,
    contract_id BIGINT UNSIGNED NOT NULL
);
