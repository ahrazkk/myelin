CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  signed_up_on TEXT NOT NULL
);

CREATE TABLE logins (
  user_id INTEGER REFERENCES users(id),
  login_date TEXT NOT NULL,
  PRIMARY KEY (user_id, login_date)
);

INSERT INTO users VALUES
  (1, 'Ali',  '2025-09-01'),
  (2, 'Bea',  '2025-09-01'),
  (3, 'Cam',  '2025-09-02'),
  (4, 'Dina', '2025-09-03'),
  (5, 'Eli',  '2025-09-04'),
  (6, 'Fay',  '2025-09-04');

INSERT INTO logins VALUES
  (1, '2025-09-01'), (1, '2025-09-02'), (1, '2025-09-03'), (1, '2025-09-05'), (1, '2025-09-06'),
  (2, '2025-09-01'), (2, '2025-09-03'), (2, '2025-09-04'),
  (3, '2025-09-02'), (3, '2025-09-03'), (3, '2025-09-04'), (3, '2025-09-05'),
  (4, '2025-09-03'), (4, '2025-09-05'),
  (5, '2025-09-04'), (5, '2025-09-05'), (5, '2025-09-06'),
  (6, '2025-09-06');
