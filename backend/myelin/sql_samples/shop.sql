CREATE TABLE customers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  joined_on TEXT NOT NULL
);

CREATE TABLE products (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price REAL NOT NULL
);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  customer_id INTEGER REFERENCES customers(id),
  ordered_on TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('delivered', 'shipped', 'cancelled'))
);

CREATE TABLE order_items (
  order_id INTEGER REFERENCES orders(id),
  product_id INTEGER REFERENCES products(id),
  quantity INTEGER NOT NULL,
  PRIMARY KEY (order_id, product_id)
);

INSERT INTO customers VALUES
  (1, 'Aisha Malik',   'Toronto',   '2025-01-05'),
  (2, 'Bruno Silva',   'Montreal',  '2025-01-20'),
  (3, 'Chloe Martin',  'Vancouver', '2025-02-11'),
  (4, 'Dev Patel',     'Toronto',   '2025-03-02'),
  (5, 'Emma Brown',    'Calgary',   '2025-03-15'),
  (6, 'Faisal Aziz',   'Ottawa',    '2025-04-01'),
  (7, 'Grace Lee',     'Toronto',   '2025-05-09'),
  (8, 'Hugo Tremblay', 'Montreal',  '2025-06-21'),
  (9, 'Iris Chen',     'Vancouver', '2025-07-30');

INSERT INTO products VALUES
  (1, 'Mechanical keyboard',         'Electronics', 129.00),
  (2, 'Noise-cancelling headphones', 'Electronics', 249.00),
  (3, 'USB-C hub',                   'Electronics',  45.50),
  (4, 'Desk lamp',                   'Home',         39.99),
  (5, 'Standing desk mat',           'Home',         59.00),
  (6, 'Notebook set',                'Stationery',   14.25),
  (7, 'Fountain pen',                'Stationery',   32.00),
  (8, 'Monitor arm',                 'Home',         89.00),
  (9, 'Webcam',                      'Electronics',  79.00);

INSERT INTO orders VALUES
  (1,  1, '2025-02-01', 'delivered'),
  (2,  2, '2025-02-14', 'delivered'),
  (3,  1, '2025-03-03', 'delivered'),
  (4,  3, '2025-03-20', 'cancelled'),
  (5,  4, '2025-03-22', 'delivered'),
  (6,  5, '2025-04-10', 'delivered'),
  (7,  4, '2025-04-18', 'shipped'),
  (8,  6, '2025-05-02', 'delivered'),
  (9,  1, '2025-05-15', 'delivered'),
  (10, 7, '2025-06-01', 'delivered'),
  (11, 3, '2025-06-12', 'delivered'),
  (12, 2, '2025-06-30', 'cancelled');

INSERT INTO order_items VALUES
  (1, 1, 1), (1, 6, 3), (2, 2, 1), (3, 3, 2), (3, 4, 1), (4, 2, 1), (5, 5, 1), (5, 7, 2),
  (6, 1, 1), (6, 3, 1), (7, 6, 5), (8, 2, 1), (8, 4, 2), (9, 7, 1), (10, 1, 2), (11, 5, 1),
  (11, 6, 2), (12, 3, 1);
