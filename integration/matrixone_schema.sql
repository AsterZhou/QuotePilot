-- MatrixOne migration DESIGN; not executed against MatrixOne.
-- Separate database credentials from Genesis token. Apply to an empty test database first.
-- Store source binaries in MOI Catalog volume; store its actual file_id below.
CREATE DATABASE IF NOT EXISTS quotepilot;
USE quotepilot;
CREATE TABLE source_files (
 id VARCHAR(64) PRIMARY KEY, email_id VARCHAR(512), parent_id VARCHAR(64),
 filename VARCHAR(1024), sha256 CHAR(64), kind VARCHAR(30), dataset VARCHAR(50),
 catalog_file_id VARCHAR(512), imported_at DATETIME
);
CREATE TABLE emails (
 email_id VARCHAR(512) PRIMARY KEY, file_hash CHAR(64), filename VARCHAR(1024),
 subject TEXT, sender TEXT, mail_date VARCHAR(100), imported_at DATETIME
);
CREATE TABLE rfq_headers (
 id BIGINT PRIMARY KEY, email_id VARCHAR(512), source_rfq_no VARCHAR(100), customer TEXT
);
CREATE TABLE rfq_lines (
 id BIGINT PRIMARY KEY, email_id VARCHAR(512), source_rfq_no VARCHAR(100),
 part_number VARCHAR(150), description TEXT, quantity BIGINT, unit VARCHAR(30),
 urgency VARCHAR(50), part_condition VARCHAR(50), mpn VARCHAR(150), deadline VARCHAR(100),
 product_scope VARCHAR(100), customer TEXT, source_kind VARCHAR(100), source_ref TEXT
);
CREATE TABLE line_evidence (line_id BIGINT PRIMARY KEY, raw_json JSON, extraction_status VARCHAR(50));
CREATE TABLE costs (
 part_number VARCHAR(150) PRIMARY KEY, description TEXT, product_scope VARCHAR(100), unit VARCHAR(30),
 inventory BIGINT, warehouse VARCHAR(100), part_condition VARCHAR(50), standard_cost DECIMAL(24,8),
 avg_cost DECIMAL(24,8), last_purchase_price DECIMAL(24,8), currency CHAR(3), updated_at VARCHAR(100), source_row VARCHAR(100)
);
CREATE TABLE prices (
 resource_id VARCHAR(100) PRIMARY KEY, part_number VARCHAR(150), supplier_code VARCHAR(100), supplier TEXT,
 `condition` VARCHAR(50), unit_price DECIMAL(24,8), currency CHAR(3), fx_to_cny DECIMAL(24,10),
 moq BIGINT, lead_days BIGINT, in_stock VARCHAR(30), certificate TEXT,
 quote_date VARCHAR(100), valid_until VARCHAR(100), status VARCHAR(50), source_row VARCHAR(100)
);
CREATE TABLE historical (
 id BIGINT PRIMARY KEY, inquiry_no VARCHAR(100), rfq_no VARCHAR(100), inquiry_date VARCHAR(100),
 airline VARCHAR(200), urgency VARCHAR(50), line_no VARCHAR(100), part_number VARCHAR(150), description TEXT,
 quantity BIGINT, unit VARCHAR(30), part_condition VARCHAR(50), product_scope VARCHAR(100), deadline VARCHAR(100), source_row VARCHAR(100)
);
CREATE TABLE quotes (id VARCHAR(100) PRIMARY KEY, created_at DATETIME, status VARCHAR(50), version BIGINT, report_json JSON, rule_version VARCHAR(100));
CREATE TABLE quote_items (quote_id VARCHAR(100), line_id BIGINT, snapshot_json JSON, PRIMARY KEY(quote_id,line_id));
CREATE TABLE audit_events (id BIGINT PRIMARY KEY, at DATETIME, action VARCHAR(100), entity_id VARCHAR(512), actor VARCHAR(100), detail_json JSON);
CREATE TABLE parse_issues (id BIGINT PRIMARY KEY, email_id VARCHAR(512), source_ref TEXT, raw_json JSON, reason TEXT);
CREATE TABLE settings (`key` VARCHAR(100) PRIMARY KEY, value_json JSON);
-- Foreign-key enforcement, index strategy, grants, JSON sizes and SQL dialect must be validated on target version.
-- Currency arithmetic continues in Python Decimal, never float/LLM.
