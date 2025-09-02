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

def login_required(f):
    @wraps(f)
    def _w(*a, **kw):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return _w

def role_required(role):
    def dec(f):
        def decorator(func):
            @wraps(func)
            def wrapper(*a, **kw):
                if session.get("role") != role:
                    abort(403)
                return func(*a, **kw)
            return wrapper
        return decorator
    return dec

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

BASE = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>RBN Viagens</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root{--blue:#0d6efd}
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;max-width:980px;margin:24px auto;padding:0 12px}
    header, nav, footer{display:flex;gap:12px;align-items:center}
    a{color:var(--blue);text-decoration:none}
    .card{border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0;background:#fff}
    .row{display:flex;gap:12px;flex-wrap:wrap}
    .row>*{flex:1}
    table{width:100%;border-collapse:collapse}
    th,td{border-bottom:1px solid #eee;padding:8px;text-align:left;font-size:14px}
    .btn{display:inline-block;padding:8px 12px;border:1px solid var(--blue);color:var(--blue);border-radius:8px;font-weight:600}
    .btn.primary{background:var(--blue);color:#fff}
    .right{margin-left:auto}
    .danger{color:#d00}
    .ok{color:#0a0}
    form input,form select,form textarea{width:100%;padding:8px;border:1px solid #ccc;border-radius:8px;font-size:14px}
    form label{font-size:12px;color:#666}
    .muted{color:#666;font-size:12px}
    .nowrap{white-space:nowrap}
  </style>
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
      <a class="danger" href="{{ url_for('logout') }}">Sair</a>
    {% else %}
      <a href="{{ url_for('login') }}">Entrar</a>
    {% endif %}
  </nav>
</header>
{% with msgs = get_flashed_messages() %}
  {% if msgs %}
    <div class="card">
      {% for m in msgs %}<div>{{ m }}</div>{% endfor %}
    </div>
  {% endif %}
{% endwith %}
<div>
  {{ body|safe }}
</div>
<footer style="margin-top:48px;color:#666">© RBN Automação</footer>
</body>
</html>
"""

def page(body, **ctx):
    return render_template_string(BASE, body=body, **ctx)

@app.route("/")
def index():
    if not session.get("user_id"):
        ensure_admin_user()
        return redirect(url_for("login"))
    return page("""
    <div class="card">
      <h3>Bem-vindo!</h3>
      <p>Use o menu para lançar despesas ou consultar viagens.</p>
    </div>
    """)

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
    return page("""
    <div class="card">
      <h3>Entrar</h3>
      <form method="post">
        <div class="row">
          <div><label>E-mail</label><input name="email" type="email" required value="admin@rbn.local"></div>
          <div><label>Senha</label><input name="password" type="password" required value="admin123"></div>
        </div>
        <p><button class="btn primary">Entrar</button></p>
        <p class="muted">Admin padrão: <code>admin@rbn.local / admin123</code> (troque depois)</p>
      </form>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin/viagens")
@login_required
@role_required("admin")
def admin_trips():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips WHERE user_id=? ORDER BY id DESC"), (session["user_id"],))
        trips = cur.fetchall()
    body = """
    <div class="card">
      <div class="row">
        <h3>Viagens (Admin)</h3>
        <a class="btn primary right" href="{{ url_for('admin_new_trip') }}">Nova viagem</a>
      </div>
      <table>
        <tr><th>ID</th><th>Título</th><th>Início</th><th>Fim</th></tr>
        {% for t in trips %}
          <tr>
            <td class="nowrap">{{ t.id }}</td>
            <td><a href="{{ url_for('trip_detail', trip_id=t.id) }}">{{ t.title }}</a></td>
            <td class="nowrap">{{ t.start_date or '' }}</td>
            <td class="nowrap">{{ t.end_date or '' }}</td>
          </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_template_string(BASE, body=body, trips=trips)

@app.route("/admin/viagens/nova", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_new_trip():
    if request.method == "POST":
        title = request.form.get("title","").strip()
        start = request.form.get("start_date") or None
        end   = request.form.get("end_date") or None
        if not title:
            flash("Informe um título.")
        else:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    q("INSERT INTO trips(title,start_date,end_date,user_id) VALUES (?,?,?,?)"),
                    (title, start, end, session["user_id"])
                )
                conn.commit()
            return redirect(url_for("admin_trips"))
    return page("""
    <div class="card">
      <h3>Nova Viagem</h3>
      <form method="post">
        <div class="row">
          <div><label>Título</label><input name="title" required></div>
          <div><label>Início</label><input type="date" name="start_date"></div>
          <div><label>Fim</label><input type="date" name="end_date"></div>
        </div>
        <p><button class="btn primary">Salvar</button>
           <a class="btn" href="{{ url_for('admin_trips') }}">Cancelar</a></p>
      </form>
    </div>
    """)

@app.route("/viagens")
@login_required
def my_trips():
    with get_conn() as conn, conn.cursor() as cur:
        if session.get("role") == "admin":
            cur.execute(q("SELECT * FROM trips WHERE user_id=? ORDER BY id DESC"), (session["user_id"],))
            trips = cur.fetchall()
            totals = {}
            for t in trips:
                cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND status!='rejeitado'"),
                            (t["id"],))
                totals[t["id"]] = cur.fetchone()["s"]
        else:
            cur.execute(q("SELECT * FROM trips ORDER BY id DESC"))
            trips = cur.fetchall()
            totals = {}
            for t in trips:
                cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND user_id=? AND status!='rejeitado'"),
                            (t["id"], session["user_id"]))
                totals[t["id"]] = cur.fetchone()["s"]

    body = """
    <div class="card">
      <h3>Viagens</h3>
      <table>
        <tr><th>ID</th><th>Título</th><th>Período</th><th class="right">Total ({{ 'meu' if session.role!='admin' else 'geral' }})</th></tr>
        {% for t in trips %}
          <tr>
            <td class="nowrap">{{ t.id }}</td>
            <td><a href="{{ url_for('trip_detail', trip_id=t.id) }}">{{ t.title }}</a></td>
            <td class="nowrap">{{ (t.start_date or '') ~ ' — ' ~ (t.end_date or '') }}</td>
            <td class="right nowrap"><b>{{ currency }} {{ '%.2f'|format(totals[t.id] or 0) }}</b></td>
          </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_template_string(BASE, body=body, trips=trips, totals=totals, currency=CURRENCY)

@app.route("/despesas/nova", methods=["GET","POST"])
@login_required
def new_expense():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips ORDER BY id DESC"))
        trips = cur.fetchall()

        if request.method == "POST":
            trip_id = request.form.get("trip_id")
            description = request.form.get("description","").strip()
            amount = parse_money(request.form.get("amount"))
            status = "pendente"

            if not trip_id:
                flash("Selecione uma viagem.")
            elif amount <= 0:
                flash("Informe um valor válido.")
            else:
                file = request.files.get("comprovante")
                url_publica = None
                if file and getattr(file, "filename", ""):
                    url_publica = upload_file(file, int(trip_id), session["user_id"])

                cur.execute(
                    q("INSERT INTO expenses (trip_id,user_id,description,amount,status,created_at,file_url) "
                      "VALUES (?,?,?,?,?,NOW(),?)"),
                    (trip_id, session["user_id"], description, str(amount), status, url_publica)
                )
                conn.commit()
                flash("Despesa lançada com sucesso.")
                return redirect(url_for("my_trips"))

    body = """
    <div class="card">
      <h3>Nova despesa</h3>
      <form method="post" enctype="multipart/form-data">
        <div class="row">
          <div>
            <label>Viagem</label>
            <select name="trip_id" required>
              <option value="">Selecione...</option>
              {% for t in trips %}
                <option value="{{ t.id }}">{{ t.id }} — {{ t.title }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label>Valor</label>
            <input name="amount" placeholder="0,00" required>
          </div>
        </div>
        <div class="row">
          <div><label>Descrição</label><input name="description" placeholder="ex.: Almoço, Combustível, etc."></div>
          <div>
            <label>Comprovante (imagem/PDF)</label>
            <input type="file" name="comprovante" accept="image/*,application/pdf" capture="environment">
            <div class="muted">Aceita foto direta da câmera.</div>
          </div>
        </div>
        <p><button class="btn primary">Lançar</button></p>
      </form>
    </div>
    """
    return render_template_string(BASE, body=body, trips=trips)

@app.route("/viagens/<int:trip_id>")
@login_required
def trip_detail(trip_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips WHERE id=?"), (trip_id,))
        t = cur.fetchone()
        if not t:
            abort(404)

        if session.get("role") == "admin":
            cur.execute(q("SELECT * FROM expenses WHERE trip_id=? ORDER BY id DESC"), (trip_id,))
            expenses = cur.fetchall()
            cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND status!='rejeitado'"),
                        (trip_id,))
            total = cur.fetchone()["s"]
        else:
            cur.execute(q("SELECT * FROM expenses WHERE trip_id=? AND user_id=? ORDER BY id DESC"),
                        (trip_id, session["user_id"]))
            expenses = cur.fetchall()
            cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND user_id=? AND status!='rejeitado'"),
                        (trip_id, session["user_id"]))
            total = cur.fetchone()["s"]

    body = """
    <div class="card">
      <div class="row">
        <h3>Viagem #{{ t.id }} — {{ t.title }}</h3>
        <span class="right muted">Período: {{ (t.start_date or '') ~ ' — ' ~ (t.end_date or '') }}</span>
      </div>
      <p><b>Total {{ 'geral' if session.role=='admin' else 'meu' }}:</b> {{ currency }} {{ '%.2f'|format(total or 0) }}</p>
      <table>
        <tr><th>ID</th><th>Data</th><th>Descrição</th><th>Valor</th><th>Comprovante</th><th>Status</th></tr>
        {% for e in expenses %}
          <tr>
            <td class="nowrap">{{ e.id }}</td>
            <td class="nowrap">{{ e.created_at }}</td>
            <td>{{ e.description or '' }}</td>
            <td class="nowrap"><b>{{ currency }} {{ '%.2f'|format(e.amount or 0) }}</b></td>
            <td>
              {% if e.file_url %}
                <a href="{{ e.file_url }}" target="_blank">abrir</a>
              {% else %}
                —
              {% endif %}
            </td>
            <td>{{ e.status }}</td>
          </tr>
        {% endfor %}
      </table>
      <p><a class="btn" href="{{ url_for('new_expense') }}">Lançar nova despesa</a></p>
    </div>
    """
    return render_template_string(BASE, body=body, t=t, expenses=expenses, total=total, currency=CURRENCY)

@app.route("/admin/usuarios/novo", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_new_user():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        role  = request.form.get("role","user")
        pwd   = request.form.get("password","")
        if not (name and email and pwd):
            flash("Preencha nome, e-mail e senha.")
        else:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(q("SELECT id FROM users WHERE email=?"), (email,))
                if cur.fetchone():
                    flash("Já existe um usuário com esse e-mail.")
                else:
                    cur.execute(q("INSERT INTO users(name,email,role,password_hash) VALUES (?,?,?,?)"),
                                (name, email, role, generate_password_hash(pwd)))
                    conn.commit()
                    flash("Usuário criado.")
                    return redirect(url_for("index"))
    return page("""
    <div class="card">
      <h3>Novo usuário</h3>
      <form method="post">
        <div class="row">
          <div><label>Nome</label><input name="name" required></div>
          <div><label>E-mail</label><input type="email" name="email" required></div>
          <div>
            <label>Papel</label>
            <select name="role"><option value="user">Funcionário</option><option value="admin">Admin</option></select>
          </div>
          <div><label>Senha</label><input type="password" name="password" required></div>
        </div>
        <p><button class="btn primary">Criar</button></p>
      </form>
    </div>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
