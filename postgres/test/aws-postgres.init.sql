-- Create Databases
CREATE DATABASE first_db;
CREATE DATABASE second_db;
CREATE DATABASE third_db;

-- Switch to first_db
\c first_db;

-- Create tables and insert data in first_db
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50),
    department VARCHAR(50),
    salary NUMERIC(10, 2)
);

INSERT INTO employees (name, department, salary)
VALUES 
    ('Alice', 'Engineering', 75000.00),
    ('Bob', 'Marketing', 55000.00),
    ('Charlie', 'HR', 60000.00);

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(100),
    start_date DATE,
    end_date DATE,
    employee_id INT REFERENCES employees(id)
);

INSERT INTO projects (project_name, start_date, end_date, employee_id)
VALUES 
    ('Project A', '2023-01-01', '2023-06-30', 1),
    ('Project B', '2023-07-01', '2023-12-31', 2),
    ('Project C', '2024-01-01', NULL, 3);

-- Switch to second_db
\c second_db;

-- Create tables and insert data in second_db
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(15)
);

INSERT INTO customers (name, email, phone)
VALUES 
    ('John Doe', 'john@example.com', '1234567890'),
    ('Jane Smith', 'jane@example.com', '9876543210'),
    ('Alice Johnson', 'alice@example.com', '5556667777');

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id), 
    order_date DATE,
    amount NUMERIC(10, 2)
);

INSERT INTO orders (customer_id, order_date, amount)
VALUES 
    (1, '2024-01-01', 250.00),
    (2, '2024-01-02', 300.00),
    (3, '2024-01-03', 150.00);

-- Switch to third_db
\c third_db;

-- Create tables and insert data in third_db
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),
    price NUMERIC(10, 2)
);

INSERT INTO products (name, category, price)
VALUES 
    ('Laptop', 'Electronics', 1000.00),
    ('Table', 'Furniture', 150.00),
    ('Pen', 'Stationery', 2.50);

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id), 
    quantity INT
);

INSERT INTO inventory (product_id, quantity)
VALUES 
    (1, 50),
    (2, 200),
    (3, 500);
