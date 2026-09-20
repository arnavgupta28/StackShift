-- acme_orders schema (MySQL 5.7)

CREATE TABLE customers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) NOT NULL,
    vip         TINYINT(1) NOT NULL DEFAULT 0,
    region      VARCHAR(8) DEFAULT 'W',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    sku         VARCHAR(32) PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    -- NULL quantity means "discontinued, stock not tracked"
    quantity    INT DEFAULT NULL,
    discontinued TINYINT(1) NOT NULL DEFAULT 0
);

CREATE TABLE orders (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    total       DECIMAL(10,2) NOT NULL,
    status      VARCHAR(32) NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    sku         VARCHAR(32) NOT NULL,
    quantity    INT NOT NULL,
    price       DECIMAL(10,2) NOT NULL
);

CREATE TABLE audit_log (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    action      VARCHAR(64) NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
