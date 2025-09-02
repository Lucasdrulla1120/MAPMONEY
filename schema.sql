
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin','user')),
  password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trips (
  id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  start_date DATE,
  end_date DATE,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS expenses (
  id SERIAL PRIMARY KEY,
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  description TEXT,
  amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pendente',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  file_url TEXT
);
CREATE TABLE IF NOT EXISTS deposits (
  id SERIAL PRIMARY KEY,
  trip_id INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  notes TEXT
);
INSERT INTO users(name,email,role,password_hash)
VALUES ('Administrador','admin@rbn.local','admin','__SET_AT_RUNTIME__')
ON CONFLICT (email) DO NOTHING;
