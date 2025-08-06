from flask import Flask, render_template, redirect, url_for, request, session, flash, send_file
import json
from functools import wraps
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'chave-secreta'
DB_PATH = 'db.json'

# ------------------------------------------
# FUNÇÕES UTILITÁRIAS
# ------------------------------------------

def carregar_dados():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"usuarios": [], "equipas": [], "jogos": []}

def salvar_dados(dados):
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=4)

# ------------------------------------------
# DECORADORES DE AUTENTICAÇÃO
# ------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated

# ------------------------------------------
# ROTAS DE AUTENTICAÇÃO
# ------------------------------------------

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        dados = carregar_dados()
        username = request.form['username']
        password = request.form['password']
        user = next((u for u in dados.get('usuarios', []) if u['username'] == username and u['password'] == password), None)
        if user:
            session['usuario'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('home'))
        else:
            flash('Credenciais inválidas.')
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------------------------------------------
# EQUIPAS
# ------------------------------------------

@app.route('/equipas')
@login_required
def listar_equipas():
    dados = carregar_dados()
    equipas = dados.get('equipas', [])
    return render_template("equipas.html", equipas=equipas)

@app.route('/adicionar_equipe', methods=['GET', 'POST'])
@admin_required
def adicionar_equipe():
    dados = carregar_dados()
    equipas = dados.get("equipas", [])
    if request.method == "POST":
        nome = request.form["nome"].strip()
        if any(e["nome"].lower() == nome.lower() for e in equipas):
            return render_template("adicionar_equipe.html", erro="Esta equipa já existe.")
        equipas.append({"nome": nome})
        dados["equipas"] = equipas
        salvar_dados(dados)
        return redirect(url_for("listar_equipas"))
    return render_template("adicionar_equipe.html")

# ------------------------------------------
# JOGOS
# ------------------------------------------

@app.route("/calendario")
@login_required
def calendario():
    dados = carregar_dados()
    jogos = dados.get("jogos", [])

    hoje = datetime.today().date()
    jogos_futuros = []
    jogos_atrasados = []

    for i, j in enumerate(jogos):
        # Ignora jogos sem campo 'data' ou 'realizado'
        if "data" not in j or j.get("realizado", False):
            continue

        try:
            # Suporta datas com ou sem hora
            try:
                data_jogo = datetime.strptime(j["data"], "%Y-%m-%dT%H:%M").date()
            except ValueError:
                data_jogo = datetime.strptime(j["data"], "%Y-%m-%d").date()

            j["id"] = i  # para ações no HTML

            if data_jogo >= hoje:
                jogos_futuros.append(j)
            else:
                jogos_atrasados.append(j)

        except Exception as e:
            # Ignora jogos com data inválida
            print(f"Erro ao processar jogo {i}: {e}")
            continue

    return render_template(
        "calendario.html",
        jogos_futuros=jogos_futuros,
        jogos_atrasados=jogos_atrasados
    )


@app.route('/jogos')
@login_required
def jogos():
    dados = carregar_dados()
    return render_template("jogos.html", jogos=dados.get('jogos', []))

@app.route("/add", methods=["GET", "POST"])
@admin_required
def adicionar_jogo():
    dados = carregar_dados()
    jogos = dados.get("jogos", [])
    equipas = dados.get("equipas", [])

    if request.method == "POST":
        time_a = request.form["time_a"]
        time_b = request.form["time_b"]
        data_jogo = request.form["data"]
        realizado = "realizado" in request.form

        if time_a == time_b:
            erro = "As equipas devem ser diferentes!"
            return render_template("add_jogo.html", erro=erro, equipas=equipas)

        # ✅ Corrigido aqui: usar data_jogo
        try:
            data_obj = datetime.strptime(data_jogo, '%Y-%m-%d')
        except ValueError:
            erro = "Data inválida."
            return render_template('add_jogo.html', erro=erro, equipas=equipas)

        # Inicializar golos
        golos_a = None
        golos_b = None

        if realizado:
            try:
                golos_a = int(request.form['golos_a'])
                golos_b = int(request.form['golos_b'])
                if golos_a < 0 or golos_b < 0:
                    raise ValueError
            except (ValueError, KeyError):
                erro = "Golos inválidos ou não informados."
                return render_template('add_jogo.html', erro=erro, equipas=equipas)

        novo_jogo = {
            "data": data_jogo,
            "time_a": time_a,
            "golos_a": golos_a,
            "time_b": time_b,
            "golos_b": golos_b,
            "realizado": realizado
        }

        jogos.append(novo_jogo)
        dados["jogos"] = jogos
        salvar_dados(dados)

        return redirect("/jogos")

    return render_template("add_jogo.html", equipas=equipas)


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_jogo(id):
    dados = carregar_dados()
    jogos = dados["jogos"]
    equipas = dados["equipas"]

    if request.method == "POST":
        time_a = request.form["time_a"]
        time_b = request.form["time_b"]
        if time_a == time_b:
            return render_template("editar_jogo.html", id=id, jogo=jogos[id], equipas=equipas, erro="As equipas devem ser diferentes.")
        jogos[id] = {
            "time_a": time_a,
            "golos_a": int(request.form["golos_a"]),
            "time_b": time_b,
            "golos_b": int(request.form["golos_b"])
        }
        salvar_dados(dados)
        return redirect(url_for('jogos'))

    return render_template("editar_jogo.html", id=id, jogo=jogos[id], equipas=equipas)

@app.route('/remover/<int:id>', methods=['POST'])
@admin_required
def remover_jogo(id):
    dados = carregar_dados()
    if 0 <= id < len(dados["jogos"]):
        dados["jogos"].pop(id)
        salvar_dados(dados)
    return redirect(url_for('jogos'))

# ------------------------------------------
# TABELA DE CLASSIFICAÇÃO
# ------------------------------------------

@app.route('/tabelas')
@login_required
def tabelas():
    dados = carregar_dados()
    jogos = dados.get("jogos", [])
    classificacao = {}

    for j in jogos:
        # Ignorar jogos incompletos
        if j.get("golos_a") is None or j.get("golos_b") is None:
            continue

        a, b = j["time_a"], j["time_b"]
        ga, gb = j["golos_a"], j["golos_b"]

        for t in [a, b]:
            if t not in classificacao:
                classificacao[t] = {"Pontos": 0, "Jogos": 0, "V": 0, "E": 0, "D": 0, "GM": 0, "GS": 0}

        classificacao[a]["Jogos"] += 1
        classificacao[b]["Jogos"] += 1
        classificacao[a]["GM"] += ga
        classificacao[a]["GS"] += gb
        classificacao[b]["GM"] += gb
        classificacao[b]["GS"] += ga

        if ga > gb:
            classificacao[a]["Pontos"] += 3
            classificacao[a]["V"] += 1
            classificacao[b]["D"] += 1
        elif gb > ga:
            classificacao[b]["Pontos"] += 3
            classificacao[b]["V"] += 1
            classificacao[a]["D"] += 1
        else:
            classificacao[a]["Pontos"] += 1
            classificacao[b]["Pontos"] += 1
            classificacao[a]["E"] += 1
            classificacao[b]["E"] += 1

    tabela = sorted(classificacao.items(), key=lambda x: x[1]["Pontos"], reverse=True)
    return render_template("tabelas.html", classificacao=tabela)


# ------------------------------------------
# EXPORTAR PDF
# ------------------------------------------

@app.route('/exportar_pdf')
@login_required
def exportar_pdf():
    dados = carregar_dados()
    jogos = dados.get("jogos", [])
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, altura - 50, "Lista de Jogos")
    y = altura - 100
    p.setFont("Helvetica", 12)
    for i, j in enumerate(jogos, 1):
        p.drawString(50, y, f"{i}. {j['time_a']} {j['golos_a']} - {j['golos_b']} {j['time_b']}")
        y -= 20
        if y < 50:
            p.showPage()
            y = altura - 50
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="jogos.pdf", mimetype="application/pdf")

@app.route("/exportar_tabela_pdf")
@login_required
def exportar_tabela_pdf():
    try:
        with open("db.json", "r") as f:
            data = json.load(f)
            jogos = data.get("jogos", [])

        classificacao = {}
        for jogo in jogos:
            a, b = jogo["time_a"], jogo["time_b"]
            ga, gb = jogo["golos_a"], jogo["golos_b"]

            for time in [a, b]:
                if time not in classificacao:
                    classificacao[time] = {"Pontos": 0, "Jogos": 0, "V": 0, "E": 0, "D": 0, "GM": 0, "GS": 0}

            classificacao[a]["Jogos"] += 1
            classificacao[b]["Jogos"] += 1
            classificacao[a]["GM"] += ga
            classificacao[a]["GS"] += gb
            classificacao[b]["GM"] += gb
            classificacao[b]["GS"] += ga

            if ga > gb:
                classificacao[a]["Pontos"] += 3
                classificacao[a]["V"] += 1
                classificacao[b]["D"] += 1
            elif gb > ga:
                classificacao[b]["Pontos"] += 3
                classificacao[b]["V"] += 1
                classificacao[a]["D"] += 1
            else:
                classificacao[a]["Pontos"] += 1
                classificacao[b]["Pontos"] += 1
                classificacao[a]["E"] += 1
                classificacao[b]["E"] += 1

        tabela = sorted(classificacao.items(), key=lambda x: x[1]["Pontos"], reverse=True)

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        largura, altura = A4

        p.setFont("Helvetica-Bold", 16)
        p.drawString(150, altura - 40, "Tabela de Classificação")

        y = altura - 80
        p.setFont("Helvetica-Bold", 12)
        p.drawString(30, y, "Pos")
        p.drawString(60, y, "Time")
        p.drawString(200, y, "P")
        p.drawString(230, y, "J")
        p.drawString(260, y, "V")
        p.drawString(290, y, "E")
        p.drawString(320, y, "D")
        p.drawString(350, y, "GM")
        p.drawString(390, y, "GS")
        p.drawString(430, y, "SG")

        p.setFont("Helvetica", 11)
        y -= 20
        for pos, (time, stats) in enumerate(tabela, start=1):
            p.drawString(30, y, str(pos))
            p.drawString(60, y, time[:18])
            p.drawString(200, y, str(stats["Pontos"]))
            p.drawString(230, y, str(stats["Jogos"]))
            p.drawString(260, y, str(stats["V"]))
            p.drawString(290, y, str(stats["E"]))
            p.drawString(320, y, str(stats["D"]))
            p.drawString(350, y, str(stats["GM"]))
            p.drawString(390, y, str(stats["GS"]))
            p.drawString(430, y, str(stats["GM"] - stats["GS"]))
            y -= 20

            if y < 50:
                p.showPage()
                y = altura - 50

        p.save()
        buffer.seek(0)

        return send_file(buffer, as_attachment=True, download_name="tabela_classificacao.pdf", mimetype="application/pdf")

    except Exception as e:
        return f"Ocorreu um erro ao gerar o PDF: {e}", 500


# ------------------------------------------
# ESTATÍSTICAS E GRÁFICOS
# ------------------------------------------

@app.route('/estatisticas')
@login_required
def estatisticas():
    dados = carregar_dados()
    jogos = dados.get("jogos", [])

    # Apenas jogos com resultado
    jogos_validos = [j for j in jogos if j.get("golos_a") is not None and j.get("golos_b") is not None]

    total_jogos = len(jogos_validos)
    total_golos = sum(j["golos_a"] + j["golos_b"] for j in jogos_validos)

    maior_goleada = max(jogos_validos, key=lambda j: abs(j["golos_a"] - j["golos_b"]), default=None)

    stats = {}
    for j in jogos_validos:
        for t, gm, gs in [(j["time_a"], j["golos_a"], j["golos_b"]), (j["time_b"], j["golos_b"], j["golos_a"])]:
            stats.setdefault(t, {"GM": 0, "GS": 0})
            stats[t]["GM"] += gm
            stats[t]["GS"] += gs

    time_mais_golos = max(stats.items(), key=lambda x: x[1]["GM"])[0] if stats else ""
    time_menos_sofreu = min(stats.items(), key=lambda x: x[1]["GS"])[0] if stats else ""

    return render_template("estatisticas.html", total_jogos=total_jogos, total_golos=total_golos,
                           maior_goleada=maior_goleada, time_mais_golos=time_mais_golos,
                           time_menos_sofreu=time_menos_sofreu)


@app.route('/graficos')
@login_required
def graficos():
    dados = carregar_dados()
    jogos = dados.get("jogos", [])
    gols = {}

    for j in jogos:
        if j.get("golos_a") is None or j.get("golos_b") is None:
            continue
        gols[j["time_a"]] = gols.get(j["time_a"], 0) + j["golos_a"]
        gols[j["time_b"]] = gols.get(j["time_b"], 0) + j["golos_b"]

    return render_template("graficos.html", times=list(gols.keys()), golos=list(gols.values()))


# ------------------------------------------
# MAIN
# ------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
