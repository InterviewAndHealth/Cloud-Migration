-- Create Databases
CREATE DATABASE first_db;
CREATE DATABASE second_db;
CREATE DATABASE third_db;

-- Switch to first_db
\c first_db;

-- Create tables in first_db
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50),
    department VARCHAR(50),
    salary NUMERIC(10, 2)
);

CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    project_name VARCHAR(100),
    start_date DATE,
    end_date DATE,
    employee_id INT REFERENCES employees(id) 
);

-- Switch to second_db
\c second_db;

-- Create tables in second_db
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50),
    email VARCHAR(100),
    phone VARCHAR(15)
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id), 
    order_date DATE,
    amount NUMERIC(10, 2)
);

-- Switch to third_db
\c third_db;

-- Create tables in third_db
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    category VARCHAR(50),
    price NUMERIC(10, 2)
);

CREATE TABLE inventory (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id),
    quantity INT
);
