CREATE TABLE departments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE employees (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  department_id INTEGER REFERENCES departments(id),
  manager_id INTEGER REFERENCES employees(id),
  salary INTEGER NOT NULL,
  hired_on TEXT NOT NULL
);

CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  department_id INTEGER REFERENCES departments(id)
);

CREATE TABLE assignments (
  employee_id INTEGER REFERENCES employees(id),
  project_id INTEGER REFERENCES projects(id),
  hours INTEGER NOT NULL,
  PRIMARY KEY (employee_id, project_id)
);

INSERT INTO departments VALUES
  (1, 'Engineering'), (2, 'Data'), (3, 'Design'), (4, 'Sales'), (5, 'Legal');

INSERT INTO employees VALUES
  (1,  'Amina Yusuf',     1, NULL, 185000, '2018-03-12'),
  (2,  'Ben Carter',      1, 1,    142000, '2019-07-01'),
  (3,  'Chen Wei',        1, 1,    142000, '2020-01-15'),
  (4,  'Dara Okafor',     1, 2,    118000, '2021-09-20'),
  (5,  'Elif Demir',      1, 2,    151000, '2022-02-01'),
  (6,  'Farah Haddad',    2, NULL, 165000, '2017-11-05'),
  (7,  'Gabe Rossi',      2, 6,    128000, '2020-06-10'),
  (8,  'Hana Sato',       2, 6,    171000, '2021-04-18'),
  (9,  'Ibrahim Khan',    2, 7,     99000, '2023-08-28'),
  (10, 'Jade Morin',      3, NULL, 132000, '2019-02-14'),
  (11, 'Kofi Mensah',     3, 10,   104000, '2022-10-03'),
  (12, 'Lena Novak',      3, 10,   104000, '2023-01-09'),
  (13, 'Malik Rahman',    4, NULL, 120000, '2016-05-23'),
  (14, 'Nora Lindqvist',  4, 13,    87000, '2021-12-01'),
  (15, 'Omar Saleh',      4, 13,    93000, '2022-07-19'),
  (16, 'Priya Nair',      4, 13,    93000, '2024-03-04');

INSERT INTO projects VALUES
  (1, 'Search', 1), (2, 'Payments', 1), (3, 'Forecasting', 2),
  (4, 'Design system', 3), (5, 'Partner portal', 4), (6, 'Archive migration', 2);

INSERT INTO assignments VALUES
  (2, 1, 120), (3, 1, 80), (4, 2, 200), (5, 2, 150), (5, 1, 40), (7, 3, 160), (8, 3, 90),
  (8, 6, 60), (9, 6, 30), (11, 4, 140), (12, 4, 110), (14, 5, 70), (15, 5, 95), (1, 2, 20);
