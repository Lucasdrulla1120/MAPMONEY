
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, render_template_string,
    session, abort, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

from db_adapter import get_conn, q
from storage_supabase import upload_file

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rbn-secret-temp")  # troque em produção

CURRENCY = "R$"

# ------------------------ Auth helpers ------------------------
def login_required(f):
    @wraps(f)
    def _w(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return _w

def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if session.get("role") != role:
                abort(403)
            return f(*a, **kw)
        return wrapper
    return decorator

def current_user():
    if not session.get("user_id"):
        return None
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM users WHERE id=?"), (session["user_id"],))
        return cur.fetchone()

def ensure_admin_user():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT id FROM users WHERE email=?"), ("admin@rbn.local",))
        row = cur.fetchone()
        if not row:
            cur.execute(
                q("INSERT INTO users(name,email,role,password_hash) VALUES (?,?,?,?)"),
                ("Administrador", "admin@rbn.local", "admin", generate_password_hash("admin123"))
            )
            conn.commit()

def parse_money(v: str) -> Decimal:
    if v is None:
        return Decimal("0")
    v = v.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return Decimal("0")

# ------------------------ HTML base ------------------------
BASE = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>RBN Viagens</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
<header>
  <h2>RBN Viagens</h2>
  <nav class="right">
    {% if session.user_id %}
      Olá, <b>{{ session.name }}</b> ({{ session.role }}) ·
      <a href="{{ url_for('index') }}">Início</a> ·
      <a href="{{ url_for('my_trips') }}">Viagens</a> ·
      <a href="{{ url_for('new_expense') }}">Nova despesa</a> ·
      {% if session.role == 'admin' %}
        <a href="{{ url_for('admin_trips') }}">Admin/Viagens</a> ·
      {% endif %}
      <a href="{{ url_for('logout') }}">Sair</a>
    {% else %}
      <a href="{{ url_for('login') }}">Entrar</a>
    {% endif %}
  </nav>
</header>
<div>{{ body|safe }}</div>
<footer>© RBN Automação</footer>
</body>
</html>
"""

def page(body, **ctx):
    return render_template_string(BASE, body=body, **ctx)

# ------------------------ Rotas ------------------------
@app.route("/")
def index():
    if not session.get("user_id"):
        ensure_admin_user()
        return redirect(url_for("login"))
    return page("<h3>Bem-vindo!</h3><p>Use o menu para lançar despesas ou consultar viagens.</p>")

@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_admin_user()
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pwd   = request.form.get("password","")
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(q("SELECT * FROM users WHERE email=?"), (email,))
            u = cur.fetchone()
            if u and check_password_hash(u["password_hash"], pwd):
                session["user_id"] = u["id"]
                session["name"] = u["name"]
                session["role"] = u["role"]
                return redirect(url_for("index"))
        flash("Credenciais inválidas.")
    return page("<form method='post'><input name='email'><input name='password'><button>Entrar</button></form>")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
