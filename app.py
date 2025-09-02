
import os
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Flask, request, redirect, url_for, render_template_string, session, abort, flash
from werkzeug.security import generate_password_hash, check_password_hash

from db_adapter import get_conn, q
from storage_supabase import upload_file

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rbn-secret-temp")

CURRENCY = "R$"

# ---------------- Helpers ----------------
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

def ensure_admin_user():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT id FROM users WHERE email=?"), ("admin@rbn.local",))
        if not cur.fetchone():
            cur.execute(q("INSERT INTO users(name,email,role,password_hash) VALUES(?,?,?,?)"),
                        ("Administrador","admin@rbn.local","admin", generate_password_hash("admin123")))
            conn.commit()

def parse_money(v: str) -> Decimal:
    if v is None: return Decimal("0")
    v = v.strip().replace(".","").replace(",",".")
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return Decimal("0")

# ---------------- Template base ----------------
BASE = """
<!doctype html><html lang=pt-br><meta charset=utf-8>
<title>RBN Viagens</title>
<meta name=viewport content="width=device-width, initial-scale=1">
<style>
:root{--b:#0d6efd}body{font-family:system-ui,-apple-system,Segoe UI,Roboto;max-width:980px;margin:24px auto;padding:0 12px}
.card{border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0}.row{display:flex;gap:12px;flex-wrap:wrap}.row>*{flex:1}
a{color:var(--b);text-decoration:none}.btn{border:1px solid var(--b);padding:8px 12px;border-radius:8px;color:var(--b)}.primary{background:var(--b);color:#fff}
.right{margin-left:auto}.muted{color:#666;font-size:12px}.nowrap{white-space:nowrap}th,td{border-bottom:1px solid #eee;padding:8px}
table{width:100%;border-collapse:collapse}
</style>
<header>
  <h2>RBN Viagens</h2>
  <nav class=right>
  {% if session.user_id %}
    Olá, <b>{{ session.name }}</b> ({{ session.role }}) ·
    <a href="{{ url_for('index') }}">Início</a> ·
    <a href="{{ url_for('my_trips') }}">Viagens</a> ·
    <a href="{{ url_for('new_expense') }}">Nova despesa</a> ·
    {% if session.role=='admin' %}<a href="{{ url_for('admin_trips') }}">Admin/Viagens</a> ·{% endif %}
    <a class=danger href="{{ url_for('logout') }}">Sair</a>
  {% else %}
    <a href="{{ url_for('login') }}">Entrar</a>
  {% endif %}
  </nav>
</header>
{% with msgs=get_flashed_messages() %}{% if msgs %}<div class=card>{% for m in msgs %}<div>{{ m }}</div>{% endfor %}</div>{% endif %}{% endwith %}
{{ body|safe }}
<footer class=muted>© RBN Automação</footer>
"""

def page(body, **ctx):
    return render_template_string(BASE, body=body, **ctx)

# ---------------- Rotas ----------------
@app.route("/")
def index():
    if not session.get("user_id"):
        ensure_admin_user()
        return redirect(url_for("login"))
    return page("""<div class=card><h3>Bem-vindo!</h3><p>Use o menu acima.</p></div>""")

@app.route("/login", methods=["GET","POST"]) 
def login():
    ensure_admin_user()
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pwd = request.form.get("password") or ""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(q("SELECT * FROM users WHERE email=?"),(email,))
            u = cur.fetchone()
            if u and check_password_hash(u["password_hash"], pwd):
                session.update({"user_id":u["id"], "name":u["name"], "role":u["role"]})
                return redirect(url_for("index"))
        flash("Credenciais inválidas.")
    return page("""
    <div class=card>
      <h3>Entrar</h3>
      <form method=post>
        <div class=row>
          <div><label>E-mail</label><input name=email type=email required value="admin@rbn.local"></div>
          <div><label>Senha</label><input name=password type=password required value="admin123"></div>
        </div>
        <p><button class="btn primary">Entrar</button></p>
      </form>
    </div>""")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Admin - listar/criar viagens do admin (viagens ficam públicas p/ funcionários)
@app.route("/admin/viagens")
@login_required
@role_required("admin")
def admin_trips():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips WHERE user_id=? ORDER BY id DESC"),(session["user_id"],))
        trips = cur.fetchall()
    body = """
    <div class=card>
      <div class=row>
        <h3>Viagens (Admin)</h3>
        <a class="btn primary right" href="{{ url_for('admin_new_trip') }}">Nova viagem</a>
      </div>
      <table><tr><th>ID</th><th>Título</th><th>Período</th></tr>
      {% for t in trips %}
        <tr>
          <td class=nowrap>{{ t.id }}</td>
          <td><a href="{{ url_for('trip_detail', trip_id=t.id) }}">{{ t.title }}</a></td>
          <td class=nowrap>{{ (t.start_date or '') ~ ' — ' ~ (t.end_date or '') }}</td>
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
        title = (request.form.get("title") or "").strip()
        start = request.form.get("start_date") or None
        end = request.form.get("end_date") or None
        if not title:
            flash("Informe um título.")
        else:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(q("INSERT INTO trips(title,start_date,end_date,user_id) VALUES (?,?,?,?)"),
                            (title, start, end, session["user_id"])) 
                conn.commit()
            return redirect(url_for("admin_trips"))
    return page("""
    <div class=card>
      <h3>Nova Viagem</h3>
      <form method=post>
        <div class=row>
          <div><label>Título</label><input name=title required></div>
          <div><label>Início</label><input type=date name=start_date></div>
          <div><label>Fim</label><input type=date name=end_date></div>
        </div>
        <p><button class="btn primary">Salvar</button>
        <a class=btn href="{{ url_for('admin_trips') }}">Cancelar</a></p>
      </form>
    </div>""")

# Lista de viagens para todos (funcionário enxerga todas)
@app.route("/viagens")
@login_required
def my_trips():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips ORDER BY id DESC"))
        trips = cur.fetchall()
        totals = {}
        for t in trips:
            if session.get("role") == "admin":
                cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND status!='rejeitado'"),(t["id"],))
            else:
                cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND user_id=? AND status!='rejeitado'"),(t["id"], session["user_id"])) 
            totals[t["id"]] = cur.fetchone()["s"]
    body = """
    <div class=card>
      <h3>Viagens</h3>
      <table>
        <tr><th>ID</th><th>Título</th><th>Período</th><th class=right>Total</th></tr>
        {% for t in trips %}
          <tr>
            <td class=nowrap>{{ t.id }}</td>
            <td><a href="{{ url_for('trip_detail', trip_id=t.id) }}">{{ t.title }}</a></td>
            <td class=nowrap>{{ (t.start_date or '') ~ ' — ' ~ (t.end_date or '') }}</td>
            <td class=right nowrap><b>{{ currency }} {{ '%.2f'|format(totals[t.id] or 0) }}</b></td>
          </tr>
        {% endfor %}
      </table>
    </div>
    """
    return render_template_string(BASE, body=body, trips=trips, totals=totals, currency=CURRENCY)

# Nova despesa (funcionário seleciona a viagem aberta)
@app.route("/despesas/nova", methods=["GET","POST"]) 
@login_required
def new_expense():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips ORDER BY id DESC"))
        trips = cur.fetchall()
        if request.method == "POST":
            trip_id = request.form.get("trip_id")
            description = (request.form.get("description") or "").strip()
            amount = parse_money(request.form.get("amount"))
            status = "pendente"
            if not trip_id:
                flash("Selecione uma viagem.")
            elif amount <= 0:
                flash("Informe um valor válido.")
            else:
                url_publica = None
                file = request.files.get("comprovante")
                if file and getattr(file, "filename", ""):
                    url_publica = upload_file(file, int(trip_id), session["user_id"])
                cur.execute(q("INSERT INTO expenses (trip_id,user_id,description,amount,status,created_at,file_url) VALUES (?,?,?,?,?,NOW(),?)"),
                            (trip_id, session["user_id"], description, str(amount), status, url_publica))
                conn.commit()
                flash("Despesa lançada.")
                return redirect(url_for("my_trips"))
    body = """
    <div class=card>
      <h3>Nova despesa</h3>
      <form method=post enctype=multipart/form-data>
        <div class=row>
          <div>
            <label>Viagem</label>
            <select name=trip_id required>
              <option value="">Selecione...</option>
              {% for t in trips %}<option value="{{ t.id }}">{{ t.id }} — {{ t.title }}</option>{% endfor %}
            </select>
          </div>
          <div><label>Valor</label><input name=amount placeholder="0,00" required></div>
        </div>
        <div class=row>
          <div><label>Descrição</label><input name=description></div>
          <div><label>Comprovante</label><input type=file name=comprovante accept="image/*,application/pdf" capture=environment></div>
        </div>
        <p><button class="btn primary">Lançar</button></p>
      </form>
    </div>
    """
    return render_template_string(BASE, body=body, trips=trips)

# Detalhe da viagem
@app.route("/viagens/<int:trip_id>") 
@login_required
def trip_detail(trip_id:int):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(q("SELECT * FROM trips WHERE id=?"),(trip_id,))
        t = cur.fetchone()
        if not t: abort(404)
        if session.get("role") == "admin":
            cur.execute(q("SELECT * FROM expenses WHERE trip_id=? ORDER BY id DESC"),(trip_id,))
            expenses = cur.fetchall()
            cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND status!='rejeitado'"),(trip_id,))
            total = cur.fetchone()["s"]
        else:
            cur.execute(q("SELECT * FROM expenses WHERE trip_id=? AND user_id=? ORDER BY id DESC"),(trip_id, session["user_id"]))
            expenses = cur.fetchall()
            cur.execute(q("SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE trip_id=? AND user_id=? AND status!='rejeitado'"),(trip_id, session["user_id"])) 
            total = cur.fetchone()["s"]
    body = """
    <div class=card>
      <div class=row><h3>Viagem #{{ t.id }} — {{ t.title }}</h3>
      <span class=right>{{ (t.start_date or '') ~ ' — ' ~ (t.end_date or '') }}</span></div>
      <p><b>Total:</b> {{ currency }} {{ '%.2f'|format(total or 0) }}</p>
      <table>
        <tr><th>ID</th><th>Data</th><th>Descrição</th><th>Valor</th><th>Comprovante</th><th>Status</th></tr>
        {% for e in expenses %}
          <tr>
            <td class=nowrap>{{ e.id }}</td>
            <td class=nowrap>{{ e.created_at }}</td>
            <td>{{ e.description or '' }}</td>
            <td class=nowrap><b>{{ currency }} {{ '%.2f'|format(e.amount or 0) }}</b></td>
            <td>{% if e.file_url %}<a href="{{ e.file_url }}" target=_blank>abrir</a>{% else %}—{% endif %}</td>
            <td>{{ e.status }}</td>
          </tr>
        {% endfor %}
      </table>
      <p><a class=btn href="{{ url_for('new_expense') }}">Lançar nova despesa</a></p>
    </div>
    """
    return render_template_string(BASE, body=body, t=t, expenses=expenses, total=total, currency=CURRENCY)

# Admin - criar usuário
@app.route("/admin/usuarios/novo", methods=["GET","POST"]) 
@login_required
@role_required("admin")
def admin_new_user():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        role = request.form.get("role") or "user"
        pwd = request.form.get("password") or ""
        if not (name and email and pwd):
            flash("Preencha nome, e-mail e senha.")
        else:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute(q("SELECT id FROM users WHERE email=?"),(email,))
                if cur.fetchone():
                    flash("Já existe um usuário com esse e-mail.")
                else:
                    cur.execute(q("INSERT INTO users(name,email,role,password_hash) VALUES (?,?,?,?)"),
                                (name, email, role, generate_password_hash(pwd)))
                    conn.commit()
                    flash("Usuário criado.")
                    return redirect(url_for("index"))
    return page("""
    <div class=card>
      <h3>Novo usuário</h3>
      <form method=post>
        <div class=row>
          <div><label>Nome</label><input name=name required></div>
          <div><label>E-mail</label><input type=email name=email required></div>
          <div><label>Papel</label><select name=role><option value=user>Funcionário</option><option value=admin>Admin</option></select></div>
          <div><label>Senha</label><input type=password name=password required></div>
        </div>
        <p><button class="btn primary">Criar</button></p>
      </form>
    </div>
    """)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8000)), debug=True)
