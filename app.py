"""Sistema de pedidos da mercearia: catálogo para clientes e painel administrativo."""

import json
import mimetypes
import os
import re
import secrets
import sqlite3
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from itertools import groupby
from pathlib import Path
from urllib.parse import quote

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

BASE = Path(__file__).resolve().parent
INSTANCE = BASE / "instance"
DB_PATH = INSTANCE / "mercearia.db"


def carregar_env(arquivo=BASE / ".env"):
    """Lê um .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas no sistema."""
    if not arquivo.exists():
        return
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip("\"'"))


carregar_env()


def numero_whatsapp(telefone):
    """Deixa só os dígitos e põe o 55 do Brasil quando o número vem só com DDD."""
    digitos = re.sub(r"\D", "", telefone or "")
    return "55" + digitos if len(digitos) in (10, 11) else digitos

STATUS = {
    "novo": "Aguardando aprovação",
    "aprovado": "Aprovado",
    "separando": "Em separação",
    "pronto": "Pronto / saiu para entrega",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}
ETAPAS = ["novo", "aprovado", "separando", "pronto", "concluido"]
STATUS_ABERTOS = ("novo", "aprovado", "separando", "pronto")
PAGAMENTOS = {
    "pix": "Pix",
    "dinheiro": "Dinheiro",
    "cartao": "Cartão (na entrega ou retirada)",
}
TAXA_ENTREGA = int(os.environ.get("MERCEARIA_TAXA_ENTREGA_CENTAVOS", "500"))
SENHA_ADMIN = os.environ.get("MERCEARIA_ADMIN_SENHA", "admin123")
# Para pagamentos via Pix: chave mostrada ao cliente e WhatsApp que recebe os comprovantes.
PIX_CHAVE = os.environ.get("MERCEARIA_PIX_CHAVE", "").strip()
WHATSAPP_LOJA = numero_whatsapp(os.environ.get("MERCEARIA_WHATSAPP"))
QTD_MAXIMA_POR_ITEM = 99

PRODUTOS_INICIAIS = [
    ("Banana prata", "Hortifrúti", 699, "kg", 40),
    ("Tomate", "Hortifrúti", 899, "kg", 30),
    ("Batata", "Hortifrúti", 599, "kg", 50),
    ("Alface crespa", "Hortifrúti", 350, "unidade", 20),
    ("Arroz branco", "Mercearia", 2890, "pacote 5 kg", 25),
    ("Feijão carioca", "Mercearia", 849, "pacote 1 kg", 40),
    ("Açúcar refinado", "Mercearia", 499, "pacote 1 kg", 30),
    ("Café torrado e moído", "Mercearia", 1990, "pacote 500 g", 20),
    ("Óleo de soja", "Mercearia", 789, "garrafa 900 ml", 35),
    ("Leite integral", "Laticínios", 549, "caixa 1 L", 60),
    ("Queijo muçarela fatiado", "Laticínios", 1290, "bandeja 200 g", 15),
    ("Manteiga com sal", "Laticínios", 1150, "pote 200 g", 15),
    ("Pão francês", "Padaria", 600, "6 unidades", 30),
    ("Bolo de fubá", "Padaria", 1600, "unidade", 8),
    ("Água mineral", "Bebidas", 300, "garrafa 1,5 L", 48),
    ("Refrigerante cola", "Bebidas", 999, "garrafa 2 L", 24),
    ("Detergente", "Limpeza", 299, "frasco 500 ml", 30),
    ("Sabão em pó", "Limpeza", 1490, "caixa 1 kg", 0),
]


def carregar_secret_key():
    INSTANCE.mkdir(exist_ok=True)
    arquivo = INSTANCE / "secret_key"
    if not arquivo.exists():
        arquivo.write_text(secrets.token_hex(32), encoding="utf-8")
    return arquivo.read_text(encoding="utf-8").strip()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("MERCEARIA_SECRET_KEY") or carregar_secret_key(),
    # "Manter conectado" no login: no celular o admin não precisa digitar a senha toda vez.
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    SESSION_COOKIE_SAMESITE="Lax",
)
# O Windows nem sempre conhece essa extensão, e o navegador espera esse tipo no manifesto.
mimetypes.add_type("application/manifest+json", ".webmanifest")


# ---------------------------------------------------------------- banco de dados

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def fechar_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    INSTANCE.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))
    if db.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO produtos (nome, categoria, preco_centavos, unidade, estoque) "
            "VALUES (?, ?, ?, ?, ?)",
            PRODUTOS_INICIAIS,
        )
    db.commit()
    db.close()


# ---------------------------------------------------------------- helpers de template

@app.template_filter("brl")
def formatar_brl(centavos):
    valor = f"{centavos / 100:,.2f}"
    return "R$ " + valor.replace(",", "_").replace(".", ",").replace("_", ".")


@app.template_filter("data_br")
def formatar_data(texto):
    # "2026-10-10 14:32:05" -> "10/10/2026 14:32"
    data, _, hora = texto.partition(" ")
    ano, mes, dia = data.split("-")
    return f"{dia}/{mes}/{ano} {hora[:5]}"


def rotulo_status(status, tipo_entrega=None):
    if status == "pronto" and tipo_entrega == "entrega":
        return "Saiu para entrega"
    if status == "pronto" and tipo_entrega == "retirada":
        return "Pronto para retirada"
    return STATUS.get(status, status)


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


app.jinja_env.globals.update(
    csrf_token=csrf_token,
    rotulo_status=rotulo_status,
    STATUS=STATUS,
    ETAPAS=ETAPAS,
    PAGAMENTOS=PAGAMENTOS,
    PIX_CONFIGURADO=bool(PIX_CHAVE or WHATSAPP_LOJA),
)


@app.before_request
def verificar_csrf():
    if request.method == "POST":
        enviado = request.form.get("csrf_token", "")
        esperado = session.get("csrf_token", "")
        if not esperado or not secrets.compare_digest(enviado, esperado):
            abort(400, "Sessão expirada. Recarregue a página e tente novamente.")


def admin_obrigatorio(view):
    @wraps(view)
    def envolvida(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return envolvida


# ---------------------------------------------------------------- área do cliente

@app.get("/")
def catalogo():
    produtos = get_db().execute(
        "SELECT * FROM produtos WHERE ativo = 1 ORDER BY categoria, nome"
    ).fetchall()
    categorias = [(cat, list(itens)) for cat, itens in groupby(produtos, key=lambda p: p["categoria"])]
    return render_template("catalogo.html", categorias=categorias)


def produtos_para_checkout():
    linhas = get_db().execute(
        "SELECT id, nome, preco_centavos, unidade, estoque FROM produtos WHERE ativo = 1"
    ).fetchall()
    return {
        str(p["id"]): {
            "nome": p["nome"],
            "preco": p["preco_centavos"],
            "unidade": p["unidade"],
            "estoque": p["estoque"],
        }
        for p in linhas
    }


@app.get("/carrinho")
def carrinho():
    return render_template(
        "carrinho.html", form={}, produtos=produtos_para_checkout(), taxa_entrega=TAXA_ENTREGA
    )


class EstoqueInsuficiente(Exception):
    pass


def ler_carrinho(texto):
    """Converte o JSON do carrinho em {produto_id: quantidade}; devolve None se inválido."""
    try:
        bruto = json.loads(texto or "{}")
        if not isinstance(bruto, dict):
            return None
        itens = {int(k): int(v) for k, v in bruto.items()}
    except (ValueError, TypeError):
        return None
    if any(q < 0 or q > QTD_MAXIMA_POR_ITEM for q in itens.values()):
        return None
    return {pid: q for pid, q in itens.items() if q > 0}


@app.post("/finalizar")
def finalizar():
    f = request.form
    nome = f.get("nome", "").strip()
    telefone = f.get("telefone", "").strip()
    tipo_entrega = f.get("tipo_entrega", "")
    endereco = f.get("endereco", "").strip()
    pagamento = f.get("pagamento", "")
    observacao = f.get("observacao", "").strip()

    erros = []
    if not nome or len(nome) > 100:
        erros.append("Informe seu nome.")
    if not 10 <= len(re.sub(r"\D", "", telefone)) <= 13:
        erros.append("Informe um telefone válido com DDD.")
    if tipo_entrega not in ("entrega", "retirada"):
        erros.append("Escolha entrega ou retirada.")
    if tipo_entrega == "entrega" and not endereco:
        erros.append("Informe o endereço de entrega.")
    if pagamento not in PAGAMENTOS:
        erros.append("Escolha a forma de pagamento.")
    if len(endereco) > 300 or len(observacao) > 500:
        erros.append("Endereço ou observação muito longos.")

    itens = ler_carrinho(f.get("carrinho"))
    if itens is None:
        erros.append("Carrinho inválido. Recarregue a página.")
        itens = {}
    elif not itens:
        erros.append("Seu carrinho está vazio.")

    db = get_db()
    produtos = {}
    if itens:
        marcadores = ",".join("?" * len(itens))
        linhas = db.execute(
            f"SELECT * FROM produtos WHERE ativo = 1 AND id IN ({marcadores})", list(itens)
        ).fetchall()
        produtos = {p["id"]: p for p in linhas}
        if len(produtos) != len(itens):
            erros.append("Algum produto do carrinho não está mais disponível. Revise o pedido.")
        for pid, qtd in itens.items():
            p = produtos.get(pid)
            if p and p["estoque"] < qtd:
                erros.append(f"Temos só {p['estoque']} de “{p['nome']}” em estoque.")

    if erros:
        for erro in erros:
            flash(erro, "erro")
        return (
            render_template(
                "carrinho.html", form=f, produtos=produtos_para_checkout(), taxa_entrega=TAXA_ENTREGA
            ),
            400,
        )

    subtotal = sum(produtos[pid]["preco_centavos"] * qtd for pid, qtd in itens.items())
    taxa = TAXA_ENTREGA if tipo_entrega == "entrega" else 0
    codigo = secrets.token_urlsafe(8)

    try:
        cursor = db.execute(
            """INSERT INTO pedidos (codigo, cliente_nome, cliente_telefone, tipo_entrega, endereco,
                   pagamento, observacao, subtotal_centavos, taxa_entrega_centavos, total_centavos)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                codigo, nome, telefone, tipo_entrega,
                endereco if tipo_entrega == "entrega" else None,
                pagamento, observacao or None, subtotal, taxa, subtotal + taxa,
            ),
        )
        pedido_id = cursor.lastrowid
        for pid, qtd in itens.items():
            p = produtos[pid]
            # Baixa condicional: protege contra dois pedidos simultâneos pelo último item.
            baixa = db.execute(
                "UPDATE produtos SET estoque = estoque - ? WHERE id = ? AND estoque >= ?",
                (qtd, pid, qtd),
            )
            if baixa.rowcount != 1:
                raise EstoqueInsuficiente(p["nome"])
            db.execute(
                """INSERT INTO itens_pedido (pedido_id, produto_id, nome_produto, unidade,
                       preco_unitario_centavos, quantidade) VALUES (?, ?, ?, ?, ?, ?)""",
                (pedido_id, pid, p["nome"], p["unidade"], p["preco_centavos"], qtd),
            )
        db.commit()
    except EstoqueInsuficiente as e:
        db.rollback()
        flash(f"“{e}” acabou de esgotar. Revise o pedido.", "erro")
        return (
            render_template(
                "carrinho.html", form=f, produtos=produtos_para_checkout(), taxa_entrega=TAXA_ENTREGA
            ),
            409,
        )

    return redirect(url_for("acompanhar_pedido", codigo=codigo, novo=1))


def carregar_pedido(where, valor):
    db = get_db()
    pedido = db.execute(f"SELECT * FROM pedidos WHERE {where} = ?", (valor,)).fetchone()
    if pedido is None:
        abort(404)
    itens = db.execute(
        "SELECT * FROM itens_pedido WHERE pedido_id = ? ORDER BY id", (pedido["id"],)
    ).fetchall()
    return pedido, itens


@app.get("/pedido/<codigo>")
def acompanhar_pedido(codigo):
    pedido, itens = carregar_pedido("codigo", codigo)
    # A chave Pix só aparece depois que a mercearia aprova o pedido, para o cliente não
    # pagar por algo que ela ainda pode recusar ou ajustar.
    pix_liberado = pedido["pagamento"] == "pix" and pedido["status"] in ("aprovado", "separando", "pronto")
    link_comprovante = None
    if pix_liberado and WHATSAPP_LOJA:
        mensagem = (
            f"Olá! Segue o comprovante do Pix do pedido #{pedido['id']} "
            f"({formatar_brl(pedido['total_centavos'])}), em nome de {pedido['cliente_nome']}.\n"
            # Quem abre este link é a mercearia, então ele leva direto ao pedido no painel.
            f"Ver no painel: {url_for('admin_pedido', pedido_id=pedido['id'], _external=True)}"
        )
        link_comprovante = f"https://wa.me/{WHATSAPP_LOJA}?text={quote(mensagem)}"
    return render_template(
        "pedido.html", pedido=pedido, itens=itens, recem_criado=request.args.get("novo") == "1",
        pix_liberado=pix_liberado, pix_chave=PIX_CHAVE, link_comprovante=link_comprovante,
    )


@app.get("/pedido/<codigo>/status")
def status_pedido(codigo):
    """Consultado periodicamente pela página do cliente para perceber mudanças de status."""
    pedido = get_db().execute(
        "SELECT status, atualizado_em FROM pedidos WHERE codigo = ?", (codigo,)
    ).fetchone()
    if pedido is None:
        abort(404)
    resposta = jsonify(status=pedido["status"], atualizado_em=pedido["atualizado_em"])
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


# ---------------------------------------------------------------- área administrativa

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("senha", ""), SENHA_ADMIN):
            session["admin"] = True
            session.permanent = request.form.get("lembrar") == "1"
            destino = request.args.get("next", "")
            if not destino.startswith("/admin/"):
                destino = url_for("admin_pedidos")
            return redirect(destino)
        flash("Senha incorreta.", "erro")
    return render_template("admin/login.html")


@app.post("/admin/sair")
def admin_sair():
    session.pop("admin", None)
    return redirect(url_for("catalogo"))


@app.get("/admin")
@admin_obrigatorio
def admin_inicio():
    return redirect(url_for("admin_pedidos"))


@app.get("/admin/pedidos")
@admin_obrigatorio
def admin_pedidos():
    filtro = request.args.get("status", "abertos")
    db = get_db()
    contagem = dict(db.execute("SELECT status, COUNT(*) FROM pedidos GROUP BY status").fetchall())
    if filtro == "abertos":
        pedidos = db.execute(
            f"SELECT * FROM pedidos WHERE status IN ({','.join('?' * len(STATUS_ABERTOS))}) ORDER BY id",
            STATUS_ABERTOS,
        ).fetchall()
    elif filtro in STATUS:
        pedidos = db.execute(
            "SELECT * FROM pedidos WHERE status = ? ORDER BY id DESC LIMIT 200", (filtro,)
        ).fetchall()
    else:
        filtro = "todos"
        pedidos = db.execute("SELECT * FROM pedidos ORDER BY id DESC LIMIT 200").fetchall()
    abertos = sum(contagem.get(s, 0) for s in STATUS_ABERTOS)
    return render_template(
        "admin/pedidos.html", pedidos=pedidos, filtro=filtro, contagem=contagem, abertos=abertos
    )


@app.get("/admin/pedidos/<int:pedido_id>")
@admin_obrigatorio
def admin_pedido(pedido_id):
    pedido, itens = carregar_pedido("id", pedido_id)
    return render_template(
        "admin/pedido.html", pedido=pedido, itens=itens,
        whatsapp=numero_whatsapp(pedido["cliente_telefone"]),
    )


@app.post("/admin/pedidos/<int:pedido_id>/status")
@admin_obrigatorio
def admin_alterar_status(pedido_id):
    novo = request.form.get("status")
    if novo not in STATUS:
        abort(400)
    db = get_db()
    pedido = db.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
    if pedido is None:
        abort(404)
    voltar = redirect(url_for("admin_pedido", pedido_id=pedido_id))
    if pedido["status"] == "cancelado":
        flash("Pedidos cancelados não mudam mais de status.", "erro")
        return voltar
    if novo == pedido["status"]:
        return voltar

    # Atualiza só se o status ainda for o que lemos, para não devolver estoque duas vezes.
    atualizado = db.execute(
        "UPDATE pedidos SET status = ?, atualizado_em = datetime('now', 'localtime') "
        "WHERE id = ? AND status = ?",
        (novo, pedido_id, pedido["status"]),
    )
    if atualizado.rowcount != 1:
        db.rollback()
        flash("O pedido foi alterado por outra pessoa. Confira e tente de novo.", "erro")
        return voltar
    if novo == "cancelado":
        db.execute(
            """UPDATE produtos SET estoque = estoque + (
                   SELECT SUM(quantidade) FROM itens_pedido
                   WHERE pedido_id = ? AND produto_id = produtos.id)
               WHERE id IN (SELECT produto_id FROM itens_pedido WHERE pedido_id = ?)""",
            (pedido_id, pedido_id),
        )
    db.commit()
    mensagem = f"Status alterado para “{rotulo_status(novo, pedido['tipo_entrega'])}”."
    if novo == "cancelado":
        mensagem += " Os itens voltaram ao estoque."
    flash(mensagem, "sucesso")
    return voltar


@app.get("/admin/produtos")
@admin_obrigatorio
def admin_produtos():
    produtos = get_db().execute("SELECT * FROM produtos ORDER BY categoria, nome").fetchall()
    return render_template("admin/produtos.html", produtos=produtos)


def ler_preco(texto):
    """Aceita "12,50", "12.50", "1.234,56" ou "R$ 12"; devolve centavos ou None."""
    texto = texto.replace("R$", "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    if valor < 0 or valor >= 1_000_000:
        return None
    return int((valor * 100).quantize(Decimal("1")))


def validar_produto(f):
    dados = {
        "nome": f.get("nome", "").strip(),
        "categoria": f.get("categoria", "").strip() or "Outros",
        "unidade": f.get("unidade", "").strip() or "unidade",
        "preco_centavos": ler_preco(f.get("preco", "")),
        "ativo": 1 if f.get("ativo") else 0,
    }
    erros = []
    if not dados["nome"] or len(dados["nome"]) > 100:
        erros.append("Informe o nome do produto (até 100 caracteres).")
    if len(dados["categoria"]) > 50 or len(dados["unidade"]) > 50:
        erros.append("Categoria e unidade aceitam até 50 caracteres.")
    if dados["preco_centavos"] is None:
        erros.append("Preço inválido. Use o formato 12,50.")
    try:
        dados["estoque"] = int(f.get("estoque", "0"))
        if dados["estoque"] < 0:
            raise ValueError
    except ValueError:
        erros.append("Estoque deve ser um número inteiro maior ou igual a zero.")
    return dados, erros


def categorias_existentes():
    return [r[0] for r in get_db().execute("SELECT DISTINCT categoria FROM produtos ORDER BY 1")]


@app.route("/admin/produtos/novo", methods=["GET", "POST"])
@admin_obrigatorio
def admin_produto_novo():
    if request.method == "POST":
        dados, erros = validar_produto(request.form)
        if not erros:
            db = get_db()
            db.execute(
                "INSERT INTO produtos (nome, categoria, preco_centavos, unidade, estoque, ativo) "
                "VALUES (:nome, :categoria, :preco_centavos, :unidade, :estoque, :ativo)",
                dados,
            )
            db.commit()
            flash(f"Produto “{dados['nome']}” cadastrado.", "sucesso")
            return redirect(url_for("admin_produtos"))
        for erro in erros:
            flash(erro, "erro")
        return render_template(
            "admin/produto_form.html", form=request.form, novo=True, categorias=categorias_existentes()
        ), 400
    return render_template(
        "admin/produto_form.html", form={"ativo": "1"}, novo=True, categorias=categorias_existentes()
    )


@app.route("/admin/produtos/<int:produto_id>/editar", methods=["GET", "POST"])
@admin_obrigatorio
def admin_produto_editar(produto_id):
    db = get_db()
    produto = db.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if produto is None:
        abort(404)
    if request.method == "POST":
        dados, erros = validar_produto(request.form)
        if not erros:
            db.execute(
                "UPDATE produtos SET nome = :nome, categoria = :categoria, "
                "preco_centavos = :preco_centavos, unidade = :unidade, estoque = :estoque, "
                "ativo = :ativo WHERE id = :id",
                {**dados, "id": produto_id},
            )
            db.commit()
            flash(f"Produto “{dados['nome']}” atualizado.", "sucesso")
            return redirect(url_for("admin_produtos"))
        for erro in erros:
            flash(erro, "erro")
        return render_template(
            "admin/produto_form.html", form=request.form, novo=False, produto=produto,
            categorias=categorias_existentes(),
        ), 400
    form = {
        "nome": produto["nome"],
        "categoria": produto["categoria"],
        "unidade": produto["unidade"],
        "preco": f"{produto['preco_centavos'] / 100:.2f}".replace(".", ","),
        "estoque": produto["estoque"],
        "ativo": "1" if produto["ativo"] else "",
    }
    return render_template(
        "admin/produto_form.html", form=form, novo=False, produto=produto,
        categorias=categorias_existentes(),
    )


@app.post("/admin/produtos/<int:produto_id>/ativo")
@admin_obrigatorio
def admin_produto_alternar(produto_id):
    db = get_db()
    db.execute("UPDATE produtos SET ativo = 1 - ativo WHERE id = ?", (produto_id,))
    db.commit()
    return redirect(url_for("admin_produtos"))


@app.post("/admin/produtos/<int:produto_id>/excluir")
@admin_obrigatorio
def admin_produto_excluir(produto_id):
    db = get_db()
    produto = db.execute("SELECT nome FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if produto is None:
        abort(404)
    # Os itens de pedidos antigos guardam nome e preço; o vínculo vira NULL (ON DELETE SET NULL).
    db.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    db.commit()
    flash(f"Produto “{produto['nome']}” excluído. Os pedidos já feitos continuam com ele.", "sucesso")
    return redirect(url_for("admin_produtos"))


@app.errorhandler(404)
def nao_encontrado(_e):
    return render_template("erro.html", titulo="Página não encontrada",
                           mensagem="O endereço que você abriu não existe."), 404


@app.errorhandler(400)
def requisicao_invalida(e):
    return render_template("erro.html", titulo="Não foi possível concluir",
                           mensagem=e.description), 400


init_db()

if __name__ == "__main__":
    host = os.environ.get("MERCEARIA_HOST", "127.0.0.1")
    porta = int(os.environ.get("MERCEARIA_PORTA", "5000"))
    if SENHA_ADMIN == "admin123":
        print("AVISO: usando a senha padrão do painel (admin123). "
              "Defina MERCEARIA_ADMIN_SENHA no arquivo .env antes de colocar no ar.")
    if os.environ.get("FLASK_DEBUG") == "1":
        app.run(host=host, port=porta, debug=True)
    else:
        from waitress import serve

        endereco = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
        print(f"Mercearia rodando em http://{endereco}:{porta}  (painel: /admin, Ctrl+C para parar)")
        if host == "0.0.0.0":
            print("Aceitando conexões de outros aparelhos da rede pelo IP desta máquina.")
        serve(app, host=host, port=porta)
