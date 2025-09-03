
import os
from flask import Flask, request, redirect, url_for, render_template_string, session
from datetime import datetime
import csv

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret")

USERS_CSV = "users.csv"
EXPENSES_CSV = "expenses.csv"

BASE = '''
<!doctype html>
<title>Controle de Viagens</title>
<h1>Controle de Viagens</h1>
{% if session.get("user") %}
<p>Logado como: {{ session['user']['name'] }} ({{ session['user']['role'] }}) | <a href="{{ url_for('logout') }}">Sair</a></p>
<hr>
<ul>
    <li><a href="{{ url_for('index') }}">Página Inicial</a></li>
    <li><a href="{{ url_for('new_expense') }}">Lançar Despesa</a></li>
    <li><a href="{{ url_for('list_expenses') }}">Consultar Despesas</a></li>
</ul>
<hr>
{{ body|safe }}
{% else %}
{{ body|safe }}
{% endif %}
'''

def page(body):
    return render_template_string(BASE, body=body)

@app.route('/')
def index():
    if not session.get("user"):
        return redirect(url_for("login"))
    return page("<h3>Bem-vindo!</h3><p>Use o menu para lançar despesas ou consultar viagens.</p>")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        with open(USERS_CSV, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['email'] == email and password in row['password_hash']:
                    session['user'] = {
                        'id': row['id'],
                        'name': row['name'],
                        'email': row['email'],
                        'role': row['role']
                    }
                    return redirect(url_for('index'))
        return page('<p>Login inválido</p><a href="/login">Tentar novamente</a>')
    return page('''
    <h3>Login</h3>
    <form method="post">
      Email: <input type="text" name="email"><br>
      Senha: <input type="password" name="password"><br>
      <input type="submit" value="Entrar">
    </form>
    ''')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/new', methods=['GET', 'POST'])
def new_expense():
    if not session.get("user"):
        return redirect(url_for("login"))
    if request.method == 'POST':
        data = {
            'user_id': session["user"]["id"],
            'descricao': request.form["descricao"],
            'valor': request.form["valor"],
            'data': request.form["data"]
        }
        file_exists = os.path.isfile(EXPENSES_CSV)
        with open(EXPENSES_CSV, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(data)
        return redirect(url_for("list_expenses"))
    return page('''
    <h3>Lançar Nova Despesa</h3>
    <form method="post">
      Descrição: <input type="text" name="descricao"><br>
      Valor: <input type="number" name="valor" step="0.01"><br>
      Data: <input type="date" name="data"><br>
      <input type="submit" value="Salvar">
    </form>
    ''')

@app.route('/list')
def list_expenses():
    if not session.get("user"):
        return redirect(url_for("login"))
    entries = []
    if os.path.isfile(EXPENSES_CSV):
        with open(EXPENSES_CSV, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['user_id'] == session["user"]["id"]:
                    entries.append(row)
    body = "<h3>Suas Despesas</h3><ul>"
    for entry in entries:
        body += f"<li>{entry['data']}: {entry['descricao']} - R$ {entry['valor']}</li>"
    body += "</ul>"
    return page(body)

if __name__ == "__main__":
    app.run(debug=True)
