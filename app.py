"""Homem grande serve paginas e API."""
import datetime
import re

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2

from db import run_query, DB_CONFIG, salvar_config

app = Flask(__name__, static_folder="static")

# nomes das paginas, homem organiza tribo
PAGES = [
    "index.html",
    "dashboard.html",
    "pedidos.html",
    "separacao_pedidos.html",
    "distribuicao_pedidos.html",
    "produtos.html",
    "vencidos.html",
    "estoque.html",
    "estoque_movimentacoes.html",
    "aquisicoes.html",
    "painel_pedidos.html",
    "pagamentos.html",
    "atas_contratos.html",
    "atas_contratos_vencidos.html",
    "cadastro.html",
    "configuracao_banco.html",
]

# paginas que aparecem no menu lateral e que um perfil de acesso pode liberar/esconder - mesma
# chave usada em ITENS_MENU (static/js/sidebar.js) pra bater o que o perfil libera com o que o
# menu desenha
PAGINAS_SISTEMA = [
    {"chave": "dashboard", "rotulo": "Dashboard"},
    {"chave": "painel_pedidos", "rotulo": "Painel de Pedidos"},
    {"chave": "pedidos", "rotulo": "Controle de Pedidos"},
    {"chave": "separacao_pedidos", "rotulo": "Separação de Pedidos"},
    {"chave": "distribuicao_pedidos", "rotulo": "Distribuição de Pedidos"},
    {"chave": "produtos", "rotulo": "Produtos"},
    {"chave": "estoque", "rotulo": "Controle de Estoque"},
    {"chave": "vencidos", "rotulo": "Produtos Vencidos"},
    {"chave": "aquisicoes", "rotulo": "Aquisições"},
    {"chave": "atas_contratos", "rotulo": "Atas e Contratos"},
    {"chave": "pagamentos", "rotulo": "Processos de Pagamento"},
    {"chave": "cadastro", "rotulo": "Cadastro"},
]
PAGINAS_SISTEMA_CHAVES = [pagina["chave"] for pagina in PAGINAS_SISTEMA]


@app.route("/")
def home():
    # porta da caverna eh o login
    return send_from_directory("pages", "index.html")


@app.route("/pages/<path:nome>")
def pages(nome):
    # abre outras salas da caverna
    if nome in PAGES:
        return send_from_directory("pages", nome)
    return "nao achado", 404


@app.route("/static/<path:caminho>")
def estatico(caminho):
    # traz pedra e osso (css/js)
    return send_from_directory("static", caminho)


def _buscar_sistemausuario(identificacao):
    linhas = run_query("""
        SELECT su.sistemausuario, su.senha_hash, su.tela_padrao, sp.sistemaperfil, sp.nome AS perfil_nome, sp.administrador
        FROM sist_logistica.sistemausuario su
        LEFT JOIN sist_logistica.sistemaperfil sp ON sp.sistemaperfil = su.sistemaperfil
        WHERE su.identificacao = %s
    """, [identificacao])
    return linhas[0] if linhas else None


def _paginas_do_perfil(sistemaperfil):
    if not sistemaperfil:
        return []
    linhas = run_query(
        "SELECT pagina FROM sist_logistica.sistemaperfilpagina WHERE sistemaperfil = %s ORDER BY pagina",
        [sistemaperfil],
    )
    return [linha["pagina"] for linha in linhas]


@app.route("/api/login", methods=["POST"])
def login():
    # confere se cacador eh da tribo: identificacao tem que existir em public.usuario (dado do
    # Guardiao) E ter um perfil atribuido em sist_logistica.sistemausuario (cadastro.html) - sem
    # perfil, sem entrada, mesmo que o Guardiao reconheca o usuario
    dados = request.get_json(force=True)
    usuario = dados.get("usuario", "").strip()
    senha = dados.get("senha", "")

    sql = """
        SELECT
            u.identificacao,
            COALESCE(pes.nome, u.nome) AS nome,
            EXISTS (
                SELECT 1 FROM public.armazemfunc af WHERE af.funcionario = u.funcionario
            ) AS tem_acesso
        FROM public.usuario u
        LEFT JOIN public.funcionario f ON f.funcionario = u.funcionario
        LEFT JOIN public.pessoafisica pf ON pf.pessoafisica = f.pessoafisica
        LEFT JOIN public.pessoa pes ON pes.pessoa = pf.pessoa
        WHERE u.identificacao = %s
    """
    linhas = run_query(sql, (usuario,))
    if not linhas:
        return jsonify({"ok": False, "msg": "usuario não encontrado"}), 401

    linha = linhas[0]
    sistemausuario = _buscar_sistemausuario(linha["identificacao"])
    if not sistemausuario or not sistemausuario["sistemaperfil"]:
        return jsonify({"ok": False, "msg": "Usuário sem perfil de acesso cadastrado. Procure o administrador."}), 403

    eh_admin = bool(sistemausuario["administrador"])
    if not eh_admin and not linha["tem_acesso"]:
        return jsonify({"ok": False, "msg": "Usuário sem acesso"}), 403

    # primeiro acesso: ainda nao tem senha definida em sistemausuario - pede pra criar antes de
    # deixar entrar (POST /api/definir_senha)
    if not sistemausuario["senha_hash"]:
        return jsonify({"ok": False, "precisa_criar_senha": True, "identificacao": linha["identificacao"]})

    if not senha or not check_password_hash(sistemausuario["senha_hash"], senha):
        return jsonify({"ok": False, "msg": "Senha incorreta"}), 401

    paginas = PAGINAS_SISTEMA_CHAVES if eh_admin else _paginas_do_perfil(sistemausuario["sistemaperfil"])

    # tela padrao (cadastro.html) decide pra onde o login manda o usuario - so vale se ainda
    # estiver dentro do que o perfil atual libera (perfil pode ter mudado desde que foi escolhida)
    tela_padrao = sistemausuario["tela_padrao"]
    if tela_padrao not in paginas:
        tela_padrao = "dashboard" if "dashboard" in paginas else (paginas[0] if paginas else None)

    # "usuario" eh o nome do funcionario pra exibir nas paginas, "identificacao" eh o login
    # (usado pra filtrar por armazem)
    return jsonify({
        "ok": True,
        "usuario": linha["nome"],
        "identificacao": linha["identificacao"],
        "administrador": eh_admin,
        "paginas": paginas,
        "tela_padrao": tela_padrao,
    })


@app.route("/api/definir_senha", methods=["POST"])
def api_definir_senha():
    # usada no primeiro acesso (sistemausuario.senha_hash ainda nulo) - so deixa definir se o
    # usuario ja tem uma linha em sistemausuario (ou seja, se um perfil ja foi atribuido a ele
    # em cadastro.html); nao cria usuario novo aqui
    dados = request.get_json(force=True)
    identificacao = (dados.get("identificacao") or "").strip()
    senha = dados.get("senha") or ""

    if not identificacao or len(senha) < 6:
        return jsonify({"ok": False, "msg": "Senha deve ter pelo menos 6 caracteres"}), 400

    sistemausuario = _buscar_sistemausuario(identificacao)
    if not sistemausuario:
        return jsonify({"ok": False, "msg": "Usuário sem perfil de acesso cadastrado. Procure o administrador."}), 403

    run_query("""
        UPDATE sist_logistica.sistemausuario
        SET senha_hash = %s, _update = now()
        WHERE identificacao = %s
    """, [generate_password_hash(senha), identificacao])

    return jsonify({"ok": True})


@app.route("/api/paginas_sistema")
def api_paginas_sistema():
    return jsonify(PAGINAS_SISTEMA)


@app.route("/api/perfis")
def api_perfis():
    perfis = run_query("""
        SELECT sistemaperfil, nome, administrador
        FROM sist_logistica.sistemaperfil
        ORDER BY nome
    """)
    for perfil in perfis:
        perfil["paginas"] = [] if perfil["administrador"] else _paginas_do_perfil(perfil["sistemaperfil"])
    return jsonify(perfis)


@app.route("/api/perfis", methods=["POST"])
def api_criar_perfil():
    dados = request.get_json(force=True)
    nome = (dados.get("nome") or "").strip()
    administrador = bool(dados.get("administrador"))
    paginas = dados.get("paginas") or []

    if not nome:
        return jsonify({"ok": False, "msg": "Informe o nome do perfil"}), 400
    if not administrador and not paginas:
        return jsonify({"ok": False, "msg": "Selecione ao menos uma página ou marque como administrador"}), 400

    try:
        linhas = run_query("""
            INSERT INTO sist_logistica.sistemaperfil (nome, administrador)
            VALUES (%s, %s)
            RETURNING sistemaperfil
        """, [nome, administrador])
        sistemaperfil = linhas[0]["sistemaperfil"]

        if not administrador:
            chaves_validas = {pagina["chave"] for pagina in PAGINAS_SISTEMA}
            for pagina in paginas:
                if pagina in chaves_validas:
                    run_query("""
                        INSERT INTO sist_logistica.sistemaperfilpagina (sistemaperfil, pagina)
                        VALUES (%s, %s)
                    """, [sistemaperfil, pagina])

        return jsonify({"ok": True, "sistemaperfil": sistemaperfil})
    except Exception as erro:
        return jsonify({"ok": False, "msg": str(erro)}), 500


@app.route("/api/perfis/<int:sistemaperfil>", methods=["PUT"])
def api_editar_perfil(sistemaperfil):
    dados = request.get_json(force=True)
    nome = (dados.get("nome") or "").strip()
    administrador = bool(dados.get("administrador"))
    paginas = dados.get("paginas") or []

    if not nome:
        return jsonify({"ok": False, "msg": "Informe o nome do perfil"}), 400
    if not administrador and not paginas:
        return jsonify({"ok": False, "msg": "Selecione ao menos uma página ou marque como administrador"}), 400

    try:
        atualizado = run_query("""
            UPDATE sist_logistica.sistemaperfil
            SET nome = %s, administrador = %s, _update = now()
            WHERE sistemaperfil = %s
            RETURNING sistemaperfil
        """, [nome, administrador, sistemaperfil])
        if not atualizado:
            return jsonify({"ok": False, "msg": "Perfil não encontrado"}), 404

        # refaz a lista de paginas do zero - mais simples que calcular diff de add/remove
        run_query("DELETE FROM sist_logistica.sistemaperfilpagina WHERE sistemaperfil = %s", [sistemaperfil])
        if not administrador:
            chaves_validas = {pagina["chave"] for pagina in PAGINAS_SISTEMA}
            for pagina in paginas:
                if pagina in chaves_validas:
                    run_query("""
                        INSERT INTO sist_logistica.sistemaperfilpagina (sistemaperfil, pagina)
                        VALUES (%s, %s)
                    """, [sistemaperfil, pagina])

        return jsonify({"ok": True})
    except Exception as erro:
        return jsonify({"ok": False, "msg": str(erro)}), 500


@app.route("/api/perfis/<int:sistemaperfil>", methods=["DELETE"])
def api_excluir_perfil(sistemaperfil):
    em_uso = run_query(
        "SELECT count(*) AS total FROM sist_logistica.sistemausuario WHERE sistemaperfil = %s",
        [sistemaperfil],
    )[0]["total"]
    if em_uso:
        return jsonify({"ok": False, "msg": f"Perfil em uso por {em_uso} usuário(s), não pode ser excluído"}), 400

    run_query("DELETE FROM sist_logistica.sistemaperfil WHERE sistemaperfil = %s", [sistemaperfil])
    return jsonify({"ok": True})


@app.route("/api/usuarios_sistema")
def api_usuarios_sistema():
    # lista usuarios do Guardiao (public.usuario) buscando por identificacao ou nome, trazendo
    # junto o perfil ja atribuido (se houver) - so busca com termo pra nao devolver as 2500+ linhas
    termo = request.args.get("termo", "").strip()
    if not termo:
        return jsonify([])

    sql = """
        SELECT
            u.identificacao,
            COALESCE(pes.nome, u.nome) AS nome,
            su.sistemaperfil,
            su.tela_padrao,
            sp.administrador
        FROM public.usuario u
        LEFT JOIN public.funcionario f ON f.funcionario = u.funcionario
        LEFT JOIN public.pessoafisica pf ON pf.pessoafisica = f.pessoafisica
        LEFT JOIN public.pessoa pes ON pes.pessoa = pf.pessoa
        LEFT JOIN sist_logistica.sistemausuario su ON su.identificacao = u.identificacao
        LEFT JOIN sist_logistica.sistemaperfil sp ON sp.sistemaperfil = su.sistemaperfil
        WHERE u.identificacao ILIKE %s OR COALESCE(pes.nome, u.nome) ILIKE %s
        ORDER BY nome
        LIMIT 20
    """
    termo_like = f"%{termo}%"
    return _consulta_generica(sql, [termo_like, termo_like])


@app.route("/api/usuarios_sistema", methods=["POST"])
def api_atribuir_perfil_usuario():
    # upsert: cria a linha em sistemausuario (sem senha - entra no fluxo de "primeiro acesso")
    # ou troca o perfil/tela padrao de quem ja tinha uma - cadastro.html sempre manda os dois
    # juntos (mesmo que so um tenha mudado), pra um nao pisar no outro
    dados = request.get_json(force=True)
    identificacao = (dados.get("identificacao") or "").strip()
    sistemaperfil = dados.get("sistemaperfil")
    tela_padrao = dados.get("tela_padrao") or None

    if not identificacao or not sistemaperfil:
        return jsonify({"ok": False, "msg": "Informe o usuário e o perfil"}), 400

    try:
        run_query("""
            INSERT INTO sist_logistica.sistemausuario (identificacao, sistemaperfil, tela_padrao)
            VALUES (%s, %s, %s)
            ON CONFLICT (identificacao)
            DO UPDATE SET sistemaperfil = EXCLUDED.sistemaperfil, tela_padrao = EXCLUDED.tela_padrao, _update = now()
        """, [identificacao, sistemaperfil, tela_padrao])
        return jsonify({"ok": True})
    except Exception as erro:
        return jsonify({"ok": False, "msg": str(erro)}), 500


@app.route("/api/usuarios_sistema/resetar_senha", methods=["POST"])
def api_resetar_senha_usuario():
    # limpa a senha (fica NULL de novo) - proximo login do usuario cai no fluxo de "primeiro
    # acesso" e pede pra ele criar uma senha nova
    dados = request.get_json(force=True)
    identificacao = (dados.get("identificacao") or "").strip()
    if not identificacao:
        return jsonify({"ok": False, "msg": "Informe o usuário"}), 400

    atualizado = run_query("""
        UPDATE sist_logistica.sistemausuario
        SET senha_hash = NULL, _update = now()
        WHERE identificacao = %s
        RETURNING sistemausuario
    """, [identificacao])
    if not atualizado:
        return jsonify({"ok": False, "msg": "Usuário sem perfil cadastrado"}), 404

    return jsonify({"ok": True})


DIAS_SEMANA_CALENDARIO = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


@app.route("/api/calendario_distribuicao")
def api_calendario_distribuicao():
    # pro armazem central escolhido, traz TODOS os armazens que constam na tabela armazem - cada
    # um com o calendario que ja esta salvo pra esse central (tudo falso se o armazem ainda nao
    # foi configurado aqui, mesmo que esteja vinculado a outro central - cada armazem so pertence
    # a um central por vez, marcar um dia aqui transfere ele pra este central)
    armazem_central = request.args.get("armazem_central")
    if not armazem_central:
        return jsonify([])

    sql = """
        SELECT
            arm.armazem,
            pes_arm.nome,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.seg, FALSE) ELSE FALSE END AS seg,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.ter, FALSE) ELSE FALSE END AS ter,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.qua, FALSE) ELSE FALSE END AS qua,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.qui, FALSE) ELSE FALSE END AS qui,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.sex, FALSE) ELSE FALSE END AS sex,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.sab, FALSE) ELSE FALSE END AS sab,
            CASE WHEN cd.armazem_central = %s THEN COALESCE(cd.dom, FALSE) ELSE FALSE END AS dom
        FROM public.armazem arm
        JOIN public.pessoa pes_arm ON arm.pessoa = pes_arm.pessoa
        LEFT JOIN sist_logistica.calendariodistribuicao cd ON cd.armazem = arm.armazem
        ORDER BY pes_arm.nome
    """
    return _consulta_generica(sql, [armazem_central] * 7)


@app.route("/api/calendario_distribuicao", methods=["POST"])
def api_salvar_calendario_distribuicao():
    dados = request.get_json(force=True)
    armazem = dados.get("armazem")
    armazem_central = dados.get("armazem_central")
    if not armazem or not armazem_central:
        return jsonify({"ok": False, "msg": "Informe o armazém e o armazém central"}), 400

    valores = [bool(dados.get(dia)) for dia in DIAS_SEMANA_CALENDARIO]

    try:
        run_query(f"""
            INSERT INTO sist_logistica.calendariodistribuicao (armazem, armazem_central, {", ".join(DIAS_SEMANA_CALENDARIO)})
            VALUES (%s, %s, {", ".join(["%s"] * len(DIAS_SEMANA_CALENDARIO))})
            ON CONFLICT (armazem)
            DO UPDATE SET armazem_central = EXCLUDED.armazem_central,
                {", ".join(f"{dia} = EXCLUDED.{dia}" for dia in DIAS_SEMANA_CALENDARIO)}, _update = now()
        """, [armazem, armazem_central, *valores])
        return jsonify({"ok": True})
    except Exception as erro:
        return jsonify({"ok": False, "msg": str(erro)}), 500


# DDL de cada tabela do schema sist_logistica (tudo CREATE ... IF NOT EXISTS - rodar de novo num
# schema que ja existe nao faz nada, so completa o que faltar numa instalacao nova). Ordem importa:
# sistemaperfil antes de quem tem FK pra ela.
TABELAS_SIST_LOGISTICA = {
    "sistemaperfil": """
        CREATE TABLE IF NOT EXISTS sist_logistica.sistemaperfil (
            sistemaperfil SERIAL PRIMARY KEY,
            nome VARCHAR(80) NOT NULL UNIQUE,
            administrador BOOLEAN NOT NULL DEFAULT FALSE,
            _creation TIMESTAMP NOT NULL DEFAULT now(),
            _update TIMESTAMP NOT NULL DEFAULT now()
        )
    """,
    "sistemaperfilpagina": """
        CREATE TABLE IF NOT EXISTS sist_logistica.sistemaperfilpagina (
            sistemaperfil INTEGER NOT NULL REFERENCES sist_logistica.sistemaperfil(sistemaperfil) ON DELETE CASCADE,
            pagina VARCHAR(80) NOT NULL,
            PRIMARY KEY (sistemaperfil, pagina)
        )
    """,
    "sistemausuario": """
        CREATE TABLE IF NOT EXISTS sist_logistica.sistemausuario (
            sistemausuario SERIAL PRIMARY KEY,
            identificacao VARCHAR(60) NOT NULL UNIQUE,
            sistemaperfil INTEGER REFERENCES sist_logistica.sistemaperfil(sistemaperfil),
            senha_hash VARCHAR(255),
            tela_padrao VARCHAR(40),
            _creation TIMESTAMP NOT NULL DEFAULT now(),
            _update TIMESTAMP NOT NULL DEFAULT now()
        )
    """,
    "calendariodistribuicao": """
        CREATE TABLE IF NOT EXISTS sist_logistica.calendariodistribuicao (
            armazem NUMERIC PRIMARY KEY,
            armazem_central NUMERIC,
            seg BOOLEAN NOT NULL DEFAULT FALSE,
            ter BOOLEAN NOT NULL DEFAULT FALSE,
            qua BOOLEAN NOT NULL DEFAULT FALSE,
            qui BOOLEAN NOT NULL DEFAULT FALSE,
            sex BOOLEAN NOT NULL DEFAULT FALSE,
            sab BOOLEAN NOT NULL DEFAULT FALSE,
            dom BOOLEAN NOT NULL DEFAULT FALSE,
            _creation TIMESTAMP NOT NULL DEFAULT now(),
            _update TIMESTAMP NOT NULL DEFAULT now()
        )
    """,
    "armazemmovimentacao": """
        CREATE TABLE IF NOT EXISTS sist_logistica.armazemmovimentacao (
            armazemmovimentacao BIGSERIAL PRIMARY KEY,
            requisicao NUMERIC,
            requisicaoitem NUMERIC,
            saidacabecalho NUMERIC NOT NULL,
            saidaitem NUMERIC,
            tipomovimentacao NUMERIC NOT NULL,
            usuario NUMERIC NOT NULL,
            unidade NUMERIC NOT NULL DEFAULT 62438,
            status CHAR(1) NOT NULL DEFAULT 'C',
            _creation TIMESTAMP NOT NULL DEFAULT now(),
            _update TIMESTAMP NOT NULL DEFAULT now()
        )
    """,
}

# indices extras (fora das PK/UNIQUE que ja saem junto com o CREATE TABLE acima)
INDICES_SIST_LOGISTICA = [
    "CREATE INDEX IF NOT EXISTS idx_armazemmov_saidacabecalho ON sist_logistica.armazemmovimentacao (saidacabecalho)",
    "CREATE INDEX IF NOT EXISTS idx_armazemmov_saidaitem ON sist_logistica.armazemmovimentacao (saidaitem)",
    "CREATE INDEX IF NOT EXISTS idx_armazemmov_usuario ON sist_logistica.armazemmovimentacao (usuario)",
]

# perfis de acesso de hoje (cadastro.html) - vira a carga inicial de um banco novo, pra nao
# comecar do zero toda vez que o schema sist_logistica eh criado numa instalacao nova
PERFIS_PADRAO = [
    {"nome": "Administrador", "administrador": True, "paginas": []},
    {"nome": "Estoquista", "administrador": False, "paginas": ["dashboard", "estoque", "produtos", "vencidos"]},
    {"nome": "Separador", "administrador": False, "paginas": ["separacao_pedidos"]},
    {"nome": "Distribuidor", "administrador": False, "paginas": ["distribuicao_pedidos"]},
    {"nome": "Administrativo", "administrador": False, "paginas": ["atas_contratos", "estoque", "pedidos", "produtos", "vencidos"]},
    {
        "nome": "Supervisor",
        "administrador": False,
        "paginas": [
            "aquisicoes", "atas_contratos", "dashboard", "distribuicao_pedidos", "estoque",
            "pagamentos", "painel_pedidos", "pedidos", "produtos", "separacao_pedidos", "vencidos",
        ],
    },
]


def _schema_sist_logistica_existe():
    linhas = run_query("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'sist_logistica'")
    return bool(linhas)


@app.route("/api/configuracao_banco")
def api_configuracao_banco():
    schema_existe = _schema_sist_logistica_existe()
    tabelas = []
    for nome in TABELAS_SIST_LOGISTICA:
        if schema_existe:
            linhas = run_query(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'sist_logistica' AND table_name = %s",
                [nome],
            )
            existe = bool(linhas)
        else:
            existe = False
        tabelas.append({"nome": nome, "existe": existe})

    return jsonify({
        "conexao": {
            "host": DB_CONFIG["host"],
            "port": DB_CONFIG["port"],
            "dbname": DB_CONFIG["dbname"],
            "user": DB_CONFIG["user"],
        },
        "schema_existe": schema_existe,
        "tabelas": tabelas,
    })


@app.route("/api/configuracao_banco", methods=["PUT"])
def api_editar_configuracao_banco():
    dados = request.get_json(force=True)
    host = (dados.get("host") or "").strip()
    porta = dados.get("port")
    dbname = (dados.get("dbname") or "").strip()
    usuario = (dados.get("user") or "").strip()
    senha = dados.get("password") or ""

    if not host or not porta or not dbname or not usuario:
        return jsonify({"ok": False, "msg": "Preencha host, porta, banco e usuário"}), 400

    try:
        porta = int(porta)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Porta inválida"}), 400

    novo_config = {"host": host, "port": porta, "dbname": dbname, "user": usuario}
    # senha em branco mantem a senha atual - evita ter que redigitar so pra trocar o host, por ex.
    novo_config["password"] = senha if senha else DB_CONFIG["password"]

    salvar_config(novo_config)
    return jsonify({"ok": True})


@app.route("/api/configuracao_banco/testar_conexao", methods=["POST"])
def api_testar_conexao_banco():
    # testa a config JA SALVA (DB_CONFIG) - pra testar valores novos, salva primeiro (editar e so
    # escrever num arquivo local, nao tem nada de destrutivo em testar antes de ter certeza)
    try:
        conexao = psycopg2.connect(connect_timeout=5, **DB_CONFIG)
        conexao.close()
        return jsonify({"ok": True, "msg": "Conexão bem-sucedida"})
    except Exception as erro:
        return jsonify({"ok": False, "msg": str(erro)}), 200


def _seed_perfis_padrao():
    # so semeia num banco novo (sistemaperfil vazio) - se ja tem perfil cadastrado nao mexe, pra
    # nao tentar duplicar nome (tem UNIQUE em sistemaperfil.nome) num banco que ja esta em uso
    total = run_query("SELECT count(*) AS total FROM sist_logistica.sistemaperfil")[0]["total"]
    if total:
        return

    for perfil in PERFIS_PADRAO:
        linhas = run_query("""
            INSERT INTO sist_logistica.sistemaperfil (nome, administrador)
            VALUES (%s, %s)
            RETURNING sistemaperfil
        """, [perfil["nome"], perfil["administrador"]])
        sistemaperfil = linhas[0]["sistemaperfil"]
        for pagina in perfil["paginas"]:
            run_query("""
                INSERT INTO sist_logistica.sistemaperfilpagina (sistemaperfil, pagina)
                VALUES (%s, %s)
            """, [sistemaperfil, pagina])


@app.route("/api/configuracao_banco/criar_schema", methods=["POST"])
def api_criar_schema_sist_logistica():
    try:
        run_query("CREATE SCHEMA IF NOT EXISTS sist_logistica")
        for ddl in TABELAS_SIST_LOGISTICA.values():
            run_query(ddl)
        for ddl in INDICES_SIST_LOGISTICA:
            run_query(ddl)
        _seed_perfis_padrao()
        return jsonify({"ok": True})
    except Exception as erro:
        return jsonify({"ok": False, "msg": str(erro)}), 500


def _consulta_generica(sql, params=None):
    # busca dado e nao briga
    try:
        return jsonify(run_query(sql, params))
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


# armazens que o usuario logado pode ver: usuario.funcionario -> funcionario.funcionario -> armazemfunc.funcionario
# (funcionario.usuario NAO serve pra isso - eh so a coluna de auditoria "quem criou o registro")
SQL_ARMAZENS_DO_USUARIO = """
    SELECT af.armazem
    FROM public.usuario u
    JOIN public.funcionario f ON f.funcionario = u.funcionario
    JOIN public.armazemfunc af ON af.funcionario = f.funcionario
    WHERE u.identificacao = %s
"""


def _usuario_eh_administrador(usuario_logado):
    if not usuario_logado:
        return False
    linhas = run_query("""
        SELECT sp.administrador
        FROM sist_logistica.sistemausuario su
        JOIN sist_logistica.sistemaperfil sp ON sp.sistemaperfil = su.sistemaperfil
        WHERE su.identificacao = %s
    """, [usuario_logado])
    return bool(linhas and linhas[0]["administrador"])


def _usuario_para_filtro_armazem(usuario_logado):
    # quem tem perfil administrador enxerga tudo, sem restricao de armazem
    if not usuario_logado or _usuario_eh_administrador(usuario_logado):
        return None
    return usuario_logado


def _resolver_usuario_id(identificacao):
    # identificacao (login) -> usuario.usuario (id numerico), usado nos inserts de armazemmovimentacao
    if not identificacao:
        return None
    linhas = run_query("SELECT usuario FROM public.usuario WHERE identificacao = %s", [identificacao])
    return linhas[0]["usuario"] if linhas else None


# tipos de movimentacao fixos da tabela armazemmovimentacao (ja existem na tipomovimentacao real)
TIPOMOV_SEPARACAO = 51743657
TIPOMOV_DISTRIBUICAO = 51743658
UNIDADE_PADRAO = 62438

# distribuicao nao trava num pedido so por vez feito a separacao - o usuario pode acumular ate 10
# pedidos reivindicados (em andamento) simultaneamente
LIMITE_DISTRIBUICAO_USUARIO = 10

# ao reivindicar (selecionar pra separacao/distribuicao), grava uma linha por item do pedido de uma
# vez so, com _creation = momento da selecao. _creation e _update saem iguais nesse insert (mesmo
# now() da transacao); concluir so atualiza _update, preservando _creation - por isso
# "_creation = _update" quer dizer "ainda em andamento" e "_creation <> _update" quer dizer "ja concluido"
SQL_PEDIDO_RECLAMADO = """
    EXISTS (
        SELECT 1 FROM sist_logistica.armazemmovimentacao am
        WHERE am.saidacabecalho = sc.saidacabecalho
        AND am.tipomovimentacao = {tipomov}
    )
""".format(tipomov=TIPOMOV_SEPARACAO)

# separacao concluida (_creation <> _update) eh o que libera o pedido pra aparecer em "pedidos
# para distribuicao" - nao precisa mais de uma linha marcadora separada pra isso
SQL_SEPARACAO_CONCLUIDA = """
    EXISTS (
        SELECT 1 FROM sist_logistica.armazemmovimentacao am
        WHERE am.saidacabecalho = sc.saidacabecalho
        AND am.tipomovimentacao = {tipomov}
        AND am._creation <> am._update
    )
""".format(tipomov=TIPOMOV_SEPARACAO)

SQL_DISTRIBUICAO_RECLAMADA = """
    EXISTS (
        SELECT 1 FROM sist_logistica.armazemmovimentacao am
        WHERE am.saidacabecalho = sc.saidacabecalho
        AND am.tipomovimentacao = {tipomov}
    )
""".format(tipomov=TIPOMOV_DISTRIBUICAO)

SQL_DISTRIBUICAO_CONCLUIDA = """
    EXISTS (
        SELECT 1 FROM sist_logistica.armazemmovimentacao am
        WHERE am.saidacabecalho = sc.saidacabecalho
        AND am.tipomovimentacao = {tipomov}
        AND am._creation <> am._update
    )
""".format(tipomov=TIPOMOV_DISTRIBUICAO)


@app.route("/api/armazens")
def api_armazens():
    sql = """
        SELECT arm.armazem, pes_arm.nome
        FROM public.armazem arm
        JOIN public.pessoa pes_arm ON arm.pessoa = pes_arm.pessoa
        WHERE arm.tipoarmazem = 'C'
        ORDER BY pes_arm.nome
    """
    return _consulta_generica(sql)


@app.route("/api/unidades")
def api_unidades():
    sql = """
        SELECT pes_rqt.nome
        FROM public.requisitante rqt
        JOIN public.pessoa pes_rqt ON rqt.pessoa = pes_rqt.pessoa
        ORDER BY pes_rqt.nome
    """
    return _consulta_generica(sql)


@app.route("/api/pedidos_novos")
def api_pedidos_novos():
    # requisicoes puras, do mais antigo pro mais novo (contrario da leitura padrao das outras
    # secoes) - se ninguem filtrar data, comeca em 01-09-2026 (janela util de dado real de teste)
    numero = request.args.get("numero")
    data_inicio = request.args.get("data_inicio") or "2026-09-01"
    data_fim = request.args.get("data_fim")
    armazem = request.args.get("armazem")
    setor = request.args.get("setor")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))

    # so entra em "novos pedidos" quem ainda nao foi tocado - se algum item da requisicao ja virou
    # saida (saidaitem), o pedido ja esta em processamento e passa a aparecer em "pedidos a separar"
    # NOT EXISTS aninhado (ri correlacionado por requisicao, depois EXISTS em si por requisicaoitem)
    # deixa o Postgres varrer so os itens das requisicoes filtradas em vez do par ri/si inteiro
    # sc.data/rq.data sao timestamp - comparar direto (sem ::date) deixa a condicao sargable, o
    # postgres consegue usar indice na coluna; ::date embrulha a coluna numa funcao e obriga
    # scan completo. limite superior vira "< dia seguinte" pra manter a mesma semantica de ::date <=
    condicoes = [
        "rq.data >= %s",
        """NOT EXISTS (
            SELECT 1 FROM public.requisicaoitem ri
            WHERE ri.requisicao = rq.requisicao
            AND EXISTS (SELECT 1 FROM public.saidaitem si WHERE si.requisicaoitem = ri.requisicaoitem)
        )""",
    ]
    params = [data_inicio]

    if numero:
        condicoes.append("rq.requisicao = %s")
        params.append(numero)
    if data_fim:
        condicoes.append("rq.data < (%s::date + INTERVAL '1 day')")
        params.append(data_fim)
    if armazem:
        condicoes.append("pes_arm.nome = %s")
        params.append(armazem)
    if setor:
        condicoes.append("pes_rqt.nome = %s")
        params.append(setor)
    if usuario_logado:
        condicoes.append(f"rq.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)

    where = f"WHERE {' AND '.join(condicoes)}"

    # o otimizador do postgres nessa base subestima quantas requisicoes passam no filtro de data
    # e escolhe fazer hash/merge join no par requisicaoitem/saidaitem inteiro (5+ milhoes de linhas)
    # em vez de so varrer os itens das requisicoes filtradas - forca nested loop so pra essa
    # consulta (SET LOCAL, vale so pra essa transacao/conexao) que com os indices fica na casa dos
    # milissegundos em vez de mais de 1 segundo
    sql = f"""
        SET LOCAL enable_hashjoin = off;
        SET LOCAL enable_mergejoin = off;
        SELECT
            rq.requisicao AS "N. do Pedido",
            pes_rqt.nome AS "Requisitante",
            (CASE EXTRACT(DOW FROM rq.data)
                WHEN 0 THEN 'Dom'
                WHEN 1 THEN 'Seg'
                WHEN 2 THEN 'Ter'
                WHEN 3 THEN 'Qua'
                WHEN 4 THEN 'Qui'
                WHEN 5 THEN 'Sex'
                WHEN 6 THEN 'Sáb'
            END || ', ' || to_char(rq.data, 'DD/MM/YY HH24:MI')) AS "Dt. da Requisição",
            CASE
                WHEN arm_rqt.armazem IS NULL THEN NULL
                ELSE COALESCE(
                    CASE EXTRACT(DOW FROM rq.data)
                        WHEN 0 THEN arm_rqt.dom
                        WHEN 1 THEN arm_rqt.seg
                        WHEN 2 THEN arm_rqt.ter
                        WHEN 3 THEN arm_rqt.qua
                        WHEN 4 THEN arm_rqt.qui
                        WHEN 5 THEN arm_rqt.sex
                        WHEN 6 THEN arm_rqt.sab
                    END, FALSE)
            END AS confere_calendario
        FROM public.requisicao rq
        JOIN public.requisitante rqt ON rq.requisitante = rqt.requisitante
        JOIN public.pessoa pes_rqt ON rqt.pessoa = pes_rqt.pessoa
        LEFT JOIN public.armazem arm ON rq.armazem = arm.armazem
        LEFT JOIN public.pessoa pes_arm ON arm.pessoa = pes_arm.pessoa
        -- conferencia requisitante x armazem: mesma pessoa.nome liga o requisitante a um
        -- armazem homonimo (ex.: requisitante "BRONCOSCOPIA" e armazem "BRONCOSCOPIA") - dai
        -- da pra checar se o calendario de distribuicao daquele armazem libera o dia do pedido.
        -- nome por si so nao eh unico na tabela pessoa inteira, entao o cruzamento parte so dos
        -- nomes de armazem (esses sim sao unicos, ja conferido) pra nao duplicar linha de pedido
        LEFT JOIN (
            SELECT pes_a.nome, arm_a.armazem, cd_a.seg, cd_a.ter, cd_a.qua, cd_a.qui, cd_a.sex, cd_a.sab, cd_a.dom
            FROM public.armazem arm_a
            JOIN public.pessoa pes_a ON pes_a.pessoa = arm_a.pessoa
            LEFT JOIN sist_logistica.calendariodistribuicao cd_a ON cd_a.armazem = arm_a.armazem
        ) arm_rqt ON arm_rqt.nome = pes_rqt.nome
        {where}
        ORDER BY rq.data ASC
    """
    return _consulta_generica(sql, params)


def _consulta_pedidos(numero=None, data_inicio=None, data_fim=None, armazem=None, setor=None, usuario_logado=None, condicoes_base=None, apenas_contagem=False):
    # pedidos a separar vem da saidacabecalho - numero do pedido = sc.saidacabecalho, requisitante
    # = pes.nome (campo pessoa da saidacabecalho), tipo de movimentacao = tipomovimentacao.descricao
    # status 'E' (estornado/cancelado) nao aparece aqui - esses vao pra lista de finalizados
    # condicoes_base troca o filtro padrao (pedidos ainda nao reivindicados pra separacao) por
    # outro - usado pra reaproveitar essa mesma consulta/SELECT na lista "para distribuicao"
    usuario_logado = _usuario_para_filtro_armazem(usuario_logado)
    condicoes = list(condicoes_base) if condicoes_base is not None else ["sc.status <> 'E'", f"NOT {SQL_PEDIDO_RECLAMADO}"]
    params = []

    if numero:
        condicoes.append("sc.saidacabecalho = %s")
        params.append(numero)
    if data_inicio:
        # sem ::date pra continuar sargable - existe indice em (status, data)
        condicoes.append("sc.data >= %s")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("sc.data < (%s::date + INTERVAL '1 day')")
        params.append(data_fim)
    if armazem:
        condicoes.append("pes_arm.nome = %s")
        params.append(armazem)
    if setor:
        condicoes.append("pes.nome = %s")
        params.append(setor)
    if usuario_logado:
        condicoes.append(f"sc.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    # apenas_contagem: usado pelos cards do painel de pedidos - mesmo WHERE, so troca o SELECT pra
    # nao trazer/ordenar a lista inteira (o painel so precisa do numero)
    base_from = """
        FROM public.saidacabecalho sc
        LEFT JOIN public.pessoa pes ON pes.pessoa = sc.pessoa
        LEFT JOIN public.tipomovimentacao tm ON tm.tipomovimentacao = sc.tipomovimentacao
        LEFT JOIN public.armazem arm ON arm.armazem = sc.armazem
        LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
    """

    if apenas_contagem:
        sql = f"SELECT count(*) AS total {base_from} {where}"
        return run_query(sql, params)[0]["total"]

    sql = f"""
        SELECT
            sc.saidacabecalho AS numero_pedido,
            pes.nome AS requisitante,
            to_char(sc.data, 'DD/MM/YY HH24:MI') AS data_requisicao,
            tm.descricao AS tipo_movimentacao,
            (SELECT count(*) FROM public.saidaitem si WHERE si.saidacabecalho = sc.saidacabecalho) AS quantidade_itens,
            (SELECT COALESCE(SUM(si.quantidade), 0) FROM public.saidaitem si WHERE si.saidacabecalho = sc.saidacabecalho) AS quantidade_total
        {base_from}
        {where}
        ORDER BY sc.data ASC
    """
    return _consulta_generica(sql, params)


@app.route("/api/saida_itens")
def api_saida_itens():
    # itens de uma saida especifica (saidaitem), carregado so quando o usuario clica na linha -
    # produto vem por estoque->lote (saidaitem.requisicaoitem nem sempre existe, mas isso sim)
    saidacabecalho = request.args.get("saidacabecalho")
    if not saidacabecalho:
        return jsonify([])

    sql = """
        SELECT
            p.nome AS nome_produto,
            si.quantidade AS quantidade,
            lt.lotefornecedor AS lote,
            to_char(lt.validade, 'DD/MM/YY') AS validade
        FROM public.saidaitem si
        LEFT JOIN public.estoque e ON e.estoque = si.estoque
        LEFT JOIN public.lote lt ON lt.lote = e.lote
        LEFT JOIN public.produto p ON p.produto = lt.produto
        WHERE si.saidacabecalho = %s
        ORDER BY p.nome
    """
    return _consulta_generica(sql, [saidacabecalho])


@app.route("/api/separacao_ativa")
def api_separacao_ativa():
    # pedido que esse usuario ja reivindicou e ainda nao concluiu (_creation = _update) - usado
    # pra bloquear "Separar Pedido" em outro pedido e mostrar a mensagem "pedido em separacao"
    usuario_id = _resolver_usuario_id(request.args.get("usuario_logado"))
    if not usuario_id:
        return jsonify(None)

    linhas = run_query(
        """
        SELECT DISTINCT am.saidacabecalho AS numero_pedido
        FROM sist_logistica.armazemmovimentacao am
        WHERE am.usuario = %s AND am.tipomovimentacao = %s AND am._creation = am._update
        LIMIT 1
        """,
        [usuario_id, TIPOMOV_SEPARACAO],
    )
    return jsonify(linhas[0] if linhas else None)


@app.route("/api/separar_pedido", methods=["POST"])
def api_separar_pedido():
    # reivindica um pedido pra separacao - so um por usuario por vez. Grava de uma vez uma linha
    # por item do pedido (requisicao/requisicaoitem/saidacabecalho/saidaitem), todas com
    # _creation = agora (o momento da selecao)
    dados = request.get_json(force=True)
    saidacabecalho = dados.get("saidacabecalho")
    usuario_id = _resolver_usuario_id(dados.get("usuario_logado"))

    if not saidacabecalho or not usuario_id:
        return jsonify({"ok": False, "msg": "dados incompletos"}), 400

    ja_reivindicado = run_query(
        """
        SELECT 1 FROM sist_logistica.armazemmovimentacao
        WHERE usuario = %s AND tipomovimentacao = %s AND _creation = _update
        LIMIT 1
        """,
        [usuario_id, TIPOMOV_SEPARACAO],
    )
    if ja_reivindicado:
        return jsonify({"ok": False, "msg": "Pedido em Separação"}), 409

    tem_item = run_query("SELECT 1 FROM public.saidaitem WHERE saidacabecalho = %s LIMIT 1", [saidacabecalho])
    if not tem_item:
        return jsonify({"ok": False, "msg": "pedido sem itens"}), 404

    # uma linha por item, de uma vez so (mesmo now() da transacao pra todo mundo) - por isso
    # requisicao/requisicaoitem/saidacabecalho/saidaitem "de todos os dados daquele pedido" ficam
    # gravados juntos, todos com _creation = o momento exato da selecao
    run_query(
        """
        INSERT INTO sist_logistica.armazemmovimentacao
            (requisicao, requisicaoitem, saidacabecalho, saidaitem, tipomovimentacao, usuario, unidade, status)
        SELECT ri.requisicao, ri.requisicaoitem, si.saidacabecalho, si.saidaitem, %s, %s, %s, 'C'
        FROM public.saidaitem si
        LEFT JOIN public.requisicaoitem ri ON ri.requisicaoitem = si.requisicaoitem
        WHERE si.saidacabecalho = %s
        """,
        [TIPOMOV_SEPARACAO, usuario_id, UNIDADE_PADRAO, saidacabecalho],
    )
    return jsonify({"ok": True})


@app.route("/api/pedidos_em_separacao")
def api_pedidos_em_separacao():
    # pedidos reivindicados e AINDA em andamento (_creation = _update) - visivel pra todo mundo,
    # nao so quem reivindicou. Uma vez concluido (_update muda), sai daqui e vai pra distribuicao
    # a consulta parte de armazemmovimentacao (tabela pequena - so reivindicacoes ativas) e so
    # depois junta com saidacabecalho pela PK - NUNCA um JOIN LATERAL correlacionado por linha de
    # saidacabecalho (tabela com mais de 1 milhao de linhas), que forcava um scan completo dela
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))

    condicoes = ["sc.status <> 'E'"]
    params = []
    if usuario_logado:
        condicoes.append(f"sc.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)

    where = f"WHERE {' AND '.join(condicoes)}"

    sql = f"""
        SELECT
            sc.saidacabecalho AS numero_pedido,
            pes.nome AS requisitante,
            to_char(sc.data, 'DD/MM/YY HH24:MI') AS data_requisicao,
            tm.descricao AS tipo_movimentacao,
            COALESCE(pes_resp.nome, u.nome) AS responsavel,
            am.usuario AS responsavel_usuario_id,
            to_char(am.min_creation, 'DD/MM/YY') AS data_separacao,
            to_char(am.min_creation, 'HH24:MI') AS hora_separacao,
            (SELECT count(*) FROM public.saidaitem si WHERE si.saidacabecalho = sc.saidacabecalho) AS quantidade_itens,
            (SELECT COALESCE(SUM(si.quantidade), 0) FROM public.saidaitem si WHERE si.saidacabecalho = sc.saidacabecalho) AS quantidade_total
        FROM (
            SELECT DISTINCT ON (am2.saidacabecalho) am2.saidacabecalho, am2.usuario, am2._creation AS min_creation
            FROM sist_logistica.armazemmovimentacao am2
            WHERE am2.tipomovimentacao = {TIPOMOV_SEPARACAO} AND am2._creation = am2._update
            ORDER BY am2.saidacabecalho, am2._creation DESC
        ) am
        JOIN public.saidacabecalho sc ON sc.saidacabecalho = am.saidacabecalho
        LEFT JOIN public.pessoa pes ON pes.pessoa = sc.pessoa
        LEFT JOIN public.tipomovimentacao tm ON tm.tipomovimentacao = sc.tipomovimentacao
        LEFT JOIN public.usuario u ON u.usuario = am.usuario
        LEFT JOIN public.funcionario f_resp ON f_resp.funcionario = u.funcionario
        LEFT JOIN public.pessoafisica pf_resp ON pf_resp.pessoafisica = f_resp.pessoafisica
        LEFT JOIN public.pessoa pes_resp ON pes_resp.pessoa = pf_resp.pessoa
        {where}
        ORDER BY sc.data ASC
    """
    return _consulta_generica(sql, params)


@app.route("/api/separacao_itens")
def api_separacao_itens():
    # itens do pedido reivindicado, com lote e validade (a marcacao de "separado" agora fica so
    # na tela, client-side - o banco so guarda o pedido inteiro reivindicado e depois concluido)
    saidacabecalho = request.args.get("saidacabecalho")
    if not saidacabecalho:
        return jsonify([])

    sql = """
        SELECT
            si.saidaitem AS saidaitem,
            p.nome AS nome_produto,
            si.quantidade AS quantidade,
            lt.lotefornecedor AS lote,
            to_char(lt.validade, 'DD/MM/YY') AS validade
        FROM public.saidaitem si
        LEFT JOIN public.estoque e ON e.estoque = si.estoque
        LEFT JOIN public.lote lt ON lt.lote = e.lote
        LEFT JOIN public.produto p ON p.produto = lt.produto
        WHERE si.saidacabecalho = %s
        ORDER BY p.nome
    """
    return _consulta_generica(sql, [saidacabecalho])


@app.route("/api/separacao_concluir", methods=["POST"])
def api_separacao_concluir():
    # so quem reivindicou (e ainda ta em andamento) pode concluir. Marcar cada item fica so na
    # tela (o pedido inteiro ja foi gravado no reivindicar) - concluir so faz o UPDATE, mantendo
    # _creation (quando foi selecionado) e trocando _update pra agora (quando foi concluido)
    dados = request.get_json(force=True)
    saidacabecalho = dados.get("saidacabecalho")
    usuario_id = _resolver_usuario_id(dados.get("usuario_logado"))

    if not saidacabecalho or not usuario_id:
        return jsonify({"ok": False, "msg": "dados incompletos"}), 400

    dono = run_query(
        """
        SELECT 1 FROM sist_logistica.armazemmovimentacao
        WHERE saidacabecalho = %s AND tipomovimentacao = %s AND usuario = %s AND _creation = _update
        LIMIT 1
        """,
        [saidacabecalho, TIPOMOV_SEPARACAO, usuario_id],
    )
    if not dono:
        return jsonify({"ok": False, "msg": "esse pedido não está reivindicado por você"}), 403

    run_query(
        """
        UPDATE sist_logistica.armazemmovimentacao
        SET _update = now()
        WHERE saidacabecalho = %s AND tipomovimentacao = %s AND usuario = %s AND _creation = _update
        """,
        [saidacabecalho, TIPOMOV_SEPARACAO, usuario_id],
    )
    # separacao concluida (_creation <> _update) ja basta pra pedido aparecer em "pedidos para
    # distribuicao" (SQL_SEPARACAO_CONCLUIDA) - nao precisa de linha marcadora extra
    return jsonify({"ok": True})


@app.route("/api/requisicao_itens")
def api_requisicao_itens():
    # itens de uma requisicao especifica, carregado so quando o usuario clica na linha
    requisicao = request.args.get("requisicao")
    if not requisicao:
        return jsonify([])

    sql = """
        SELECT
            p.nome AS nome_produto,
            ri.quantidade AS quantidade
        FROM public.requisicaoitem ri
        JOIN public.produto p ON p.produto = ri.produto
        WHERE ri.requisicao = %s
        ORDER BY p.nome
    """
    return _consulta_generica(sql, [requisicao])


@app.route("/api/pedidos_separacao")
def api_pedidos_separacao():
    # TODO homem: falta status/separacao/distribuicao - so numero, data, armazem e setor estao ligados por enquanto
    return _consulta_pedidos(
        numero=request.args.get("numero"),
        data_inicio=request.args.get("data_inicio"),
        data_fim=request.args.get("data_fim"),
        armazem=request.args.get("armazem"),
        setor=request.args.get("setor"),
        usuario_logado=request.args.get("usuario_logado"),
    )


@app.route("/api/pedidos_distribuicao")
def api_pedidos_distribuicao():
    # "pedidos para distribuicao": separacao ja concluida e ainda nao reivindicado pra distribuicao
    # (mesmo SELECT/FROM de _consulta_pedidos, so troca o filtro padrao de "nao reivindicado pra
    # separacao" por "separacao concluida e nao reivindicado pra distribuicao")
    return _consulta_pedidos(
        numero=request.args.get("numero"),
        data_inicio=request.args.get("data_inicio"),
        data_fim=request.args.get("data_fim"),
        armazem=request.args.get("armazem"),
        setor=request.args.get("setor"),
        usuario_logado=request.args.get("usuario_logado"),
        condicoes_base=["sc.status <> 'E'", SQL_SEPARACAO_CONCLUIDA, f"NOT {SQL_DISTRIBUICAO_RECLAMADA}"],
    )


@app.route("/api/pedidos_em_distribuicao")
def api_pedidos_em_distribuicao():
    # pedidos reivindicados pra distribuicao e AINDA em andamento (_creation = _update) - visivel
    # pra todo mundo, igual pedidos_em_separacao. Uma vez concluido, sai daqui e vai pra finalizados
    # mesma logica de performance: parte de armazemmovimentacao (pequena) e so depois junta com
    # saidacabecalho pela PK, nunca um JOIN LATERAL correlacionado por linha de saidacabecalho
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))

    condicoes = ["sc.status <> 'E'"]
    params = []
    if usuario_logado:
        condicoes.append(f"sc.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)

    where = f"WHERE {' AND '.join(condicoes)}"

    sql = f"""
        SELECT
            sc.saidacabecalho AS numero_pedido,
            pes.nome AS requisitante,
            to_char(sc.data, 'DD/MM/YY HH24:MI') AS data_requisicao,
            tm.descricao AS tipo_movimentacao,
            COALESCE(pes_resp.nome, u.nome) AS responsavel,
            am.usuario AS responsavel_usuario_id,
            to_char(am.min_creation, 'DD/MM/YY') AS data_distribuicao,
            to_char(am.min_creation, 'HH24:MI') AS hora_distribuicao,
            (SELECT count(*) FROM public.saidaitem si WHERE si.saidacabecalho = sc.saidacabecalho) AS quantidade_itens,
            (SELECT COALESCE(SUM(si.quantidade), 0) FROM public.saidaitem si WHERE si.saidacabecalho = sc.saidacabecalho) AS quantidade_total
        FROM (
            SELECT DISTINCT ON (am2.saidacabecalho) am2.saidacabecalho, am2.usuario, am2._creation AS min_creation
            FROM sist_logistica.armazemmovimentacao am2
            WHERE am2.tipomovimentacao = {TIPOMOV_DISTRIBUICAO} AND am2._creation = am2._update
            ORDER BY am2.saidacabecalho, am2._creation DESC
        ) am
        JOIN public.saidacabecalho sc ON sc.saidacabecalho = am.saidacabecalho
        LEFT JOIN public.pessoa pes ON pes.pessoa = sc.pessoa
        LEFT JOIN public.tipomovimentacao tm ON tm.tipomovimentacao = sc.tipomovimentacao
        LEFT JOIN public.usuario u ON u.usuario = am.usuario
        LEFT JOIN public.funcionario f_resp ON f_resp.funcionario = u.funcionario
        LEFT JOIN public.pessoafisica pf_resp ON pf_resp.pessoafisica = f_resp.pessoafisica
        LEFT JOIN public.pessoa pes_resp ON pes_resp.pessoa = pf_resp.pessoa
        {where}
        ORDER BY sc.data ASC
    """
    return _consulta_generica(sql, params)


@app.route("/api/distribuicao_ativos")
def api_distribuicao_ativos():
    # pedidos que esse usuario ja reivindicou pra distribuicao e ainda estao em andamento - usado
    # pra saber quantas vagas restam (limite de 10 simultaneos) e travar os checkboxes na tela
    usuario_id = _resolver_usuario_id(request.args.get("usuario_logado"))
    if not usuario_id:
        return jsonify([])

    linhas = run_query(
        """
        SELECT DISTINCT am.saidacabecalho AS numero_pedido
        FROM sist_logistica.armazemmovimentacao am
        WHERE am.usuario = %s AND am.tipomovimentacao = %s AND am._creation = am._update
        """,
        [usuario_id, TIPOMOV_DISTRIBUICAO],
    )
    return jsonify(linhas)


@app.route("/api/distribuir_pedidos", methods=["POST"])
def api_distribuir_pedidos():
    # reivindica ate 10 pedidos de uma vez pra distribuicao (diferente da separacao, que trava em
    # 1 por vez). Conta quantos esse usuario ja tem em andamento e nao deixa passar do limite
    dados = request.get_json(force=True)
    saidacabecalhos = dados.get("saidacabecalhos") or []
    usuario_id = _resolver_usuario_id(dados.get("usuario_logado"))

    if not saidacabecalhos or not usuario_id:
        return jsonify({"ok": False, "msg": "dados incompletos"}), 400

    try:
        saidacabecalhos = [int(numero) for numero in saidacabecalhos]
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "pedido inválido"}), 400

    ja_ativos = run_query(
        """
        SELECT DISTINCT saidacabecalho FROM sist_logistica.armazemmovimentacao
        WHERE usuario = %s AND tipomovimentacao = %s AND _creation = _update
        """,
        [usuario_id, TIPOMOV_DISTRIBUICAO],
    )
    vagas = LIMITE_DISTRIBUICAO_USUARIO - len(ja_ativos)
    if len(saidacabecalhos) > vagas:
        return jsonify({
            "ok": False,
            "msg": f"Você só pode pegar mais {vagas} pedido(s) pra distribuição agora (limite de {LIMITE_DISTRIBUICAO_USUARIO} simultâneos)."
        }), 409

    ja_reivindicados = run_query(
        """
        SELECT DISTINCT saidacabecalho FROM sist_logistica.armazemmovimentacao
        WHERE tipomovimentacao = %s AND saidacabecalho = ANY(%s)
        """,
        [TIPOMOV_DISTRIBUICAO, saidacabecalhos],
    )
    if ja_reivindicados:
        numeros = ", ".join(str(linha["saidacabecalho"]) for linha in ja_reivindicados)
        return jsonify({"ok": False, "msg": f"Pedido(s) já reivindicado(s) pra distribuição: {numeros}"}), 409

    # mesma logica da separacao: uma linha por item de cada pedido, todas de uma vez (mesmo now())
    run_query(
        """
        INSERT INTO sist_logistica.armazemmovimentacao
            (requisicao, requisicaoitem, saidacabecalho, saidaitem, tipomovimentacao, usuario, unidade, status)
        SELECT ri.requisicao, ri.requisicaoitem, si.saidacabecalho, si.saidaitem, %s, %s, %s, 'C'
        FROM public.saidaitem si
        LEFT JOIN public.requisicaoitem ri ON ri.requisicaoitem = si.requisicaoitem
        WHERE si.saidacabecalho = ANY(%s)
        """,
        [TIPOMOV_DISTRIBUICAO, usuario_id, UNIDADE_PADRAO, saidacabecalhos],
    )
    return jsonify({"ok": True})


@app.route("/api/distribuicao_itens")
def api_distribuicao_itens():
    # itens do pedido reivindicado pra distribuicao, com lote e validade - marcacao de "separado"
    # fica so na tela, igual a separacao
    saidacabecalho = request.args.get("saidacabecalho")
    if not saidacabecalho:
        return jsonify([])

    sql = """
        SELECT
            si.saidaitem AS saidaitem,
            p.nome AS nome_produto,
            si.quantidade AS quantidade,
            lt.lotefornecedor AS lote,
            to_char(lt.validade, 'DD/MM/YY') AS validade
        FROM public.saidaitem si
        LEFT JOIN public.estoque e ON e.estoque = si.estoque
        LEFT JOIN public.lote lt ON lt.lote = e.lote
        LEFT JOIN public.produto p ON p.produto = lt.produto
        WHERE si.saidacabecalho = %s
        ORDER BY p.nome
    """
    return _consulta_generica(sql, [saidacabecalho])


@app.route("/api/distribuicao_concluir", methods=["POST"])
def api_distribuicao_concluir():
    # so quem reivindicou (e ainda ta em andamento) pode concluir esse pedido especifico - cada
    # pedido reivindicado se conclui de forma independente (nao trava os outros 9)
    dados = request.get_json(force=True)
    saidacabecalho = dados.get("saidacabecalho")
    usuario_id = _resolver_usuario_id(dados.get("usuario_logado"))

    if not saidacabecalho or not usuario_id:
        return jsonify({"ok": False, "msg": "dados incompletos"}), 400

    dono = run_query(
        """
        SELECT 1 FROM sist_logistica.armazemmovimentacao
        WHERE saidacabecalho = %s AND tipomovimentacao = %s AND usuario = %s AND _creation = _update
        LIMIT 1
        """,
        [saidacabecalho, TIPOMOV_DISTRIBUICAO, usuario_id],
    )
    if not dono:
        return jsonify({"ok": False, "msg": "esse pedido não está reivindicado por você"}), 403

    run_query(
        """
        UPDATE sist_logistica.armazemmovimentacao
        SET _update = now()
        WHERE saidacabecalho = %s AND tipomovimentacao = %s AND usuario = %s AND _creation = _update
        """,
        [saidacabecalho, TIPOMOV_DISTRIBUICAO, usuario_id],
    )
    return jsonify({"ok": True})


@app.route("/api/pedidos_finalizados")
def api_pedidos_finalizados():
    # cancelados (saidacabecalho.status = 'E', estornado) + pedidos que ja concluiram a
    # distribuicao (_creation <> _update na linha de distribuicao)
    numero = request.args.get("numero")
    data_inicio = request.args.get("data_inicio") or "2026-09-01"
    data_fim = request.args.get("data_fim")
    armazem = request.args.get("armazem")
    setor = request.args.get("setor")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))

    # sem ::date pra continuar sargable (indice em (status, data))
    condicoes = [f"(sc.status = 'E' OR {SQL_DISTRIBUICAO_CONCLUIDA})", "sc.data >= %s"]
    params = [data_inicio]

    if numero:
        condicoes.append("sc.saidacabecalho = %s")
        params.append(numero)
    if data_fim:
        condicoes.append("sc.data < (%s::date + INTERVAL '1 day')")
        params.append(data_fim)
    if armazem:
        condicoes.append("pes_arm.nome = %s")
        params.append(armazem)
    if setor:
        condicoes.append("pes.nome = %s")
        params.append(setor)
    if usuario_logado:
        condicoes.append(f"sc.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)

    where = f"WHERE {' AND '.join(condicoes)}"

    sql = f"""
        SELECT
            sc.saidacabecalho AS "N. do Pedido",
            pes.nome AS "Requisitante",
            to_char(sc.data, 'DD/MM/YY HH24:MI') AS "Dt. da Requisição",
            tm.descricao AS "Tipo de Movimentação",
            CASE WHEN sc.status = 'E' THEN 'Cancelado' ELSE 'Concluído' END AS "Status"
        FROM public.saidacabecalho sc
        LEFT JOIN public.pessoa pes ON pes.pessoa = sc.pessoa
        LEFT JOIN public.tipomovimentacao tm ON tm.tipomovimentacao = sc.tipomovimentacao
        LEFT JOIN public.armazem arm ON arm.armazem = sc.armazem
        LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
        {where}
        ORDER BY sc.data ASC
    """
    return _consulta_generica(sql, params)


@app.route("/api/separacao_pedidos")
def api_separacao_pedidos():
    return _consulta_pedidos(
        numero=request.args.get("numero"),
        data_inicio=request.args.get("data_inicio"),
        data_fim=request.args.get("data_fim"),
        setor=request.args.get("unidade"),
        usuario_logado=request.args.get("usuario_logado"),
    )


@app.route("/api/produtos_sugestoes")
def api_produtos_sugestoes():
    # nome vai digitando, essa rota devolve so um punhado pra lista de sugestao
    termo = request.args.get("termo", "").strip()
    if not termo:
        return jsonify([])

    sql = """
        SELECT produto AS cod_produto, nome AS nome_produto
        FROM public.produto
        WHERE nome ILIKE %s
        ORDER BY nome
        LIMIT 10
    """
    return _consulta_generica(sql, [f"%{termo}%"])


@app.route("/api/subgrupos_sugestoes")
def api_subgrupos_sugestoes():
    # nome vai digitando, essa rota devolve so um punhado pra lista de sugestao
    termo = request.args.get("termo", "").strip()
    if not termo:
        return jsonify([])

    sql = """
        SELECT DISTINCT descricao AS sub_grupo
        FROM public.subgrupo
        WHERE descricao ILIKE %s
        ORDER BY descricao
        LIMIT 10
    """
    return _consulta_generica(sql, [f"%{termo}%"])


@app.route("/api/fornecedores_sugestoes")
def api_fornecedores_sugestoes():
    # nome vai digitando, essa rota devolve so um punhado pra lista de sugestao
    termo = request.args.get("termo", "").strip()
    if not termo:
        return jsonify([])

    sql = """
        SELECT DISTINCT pes.nome AS fornecedor
        FROM public.fornecedor forn
        JOIN public.pessoa pes ON pes.pessoa = forn.pessoa
        WHERE pes.nome ILIKE %s
        ORDER BY pes.nome
        LIMIT 10
    """
    return _consulta_generica(sql, [f"%{termo}%"])


@app.route("/api/produtos")
def api_produtos():
    # um produto por linha (sem join com lote/estoque, que duplicava por causa dos varios lotes) -
    # lote e quantidade por lote vem por fora, sob demanda, em /api/produtos_lotes
    cod_seplag = request.args.get("cod_seplag")
    cod_almox = request.args.get("cod_almox")
    cod_produto = request.args.get("cod_produto")
    nome_produto = request.args.get("nome_produto")
    lote = request.args.get("lote")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    try:
        pagina = max(int(request.args.get("pagina", 1)), 1)
    except ValueError:
        pagina = 1

    condicoes = []
    params = []

    if cod_seplag:
        condicoes.append("p.codigoreferencia ILIKE %s")
        params.append(f"%{cod_seplag}%")
    if cod_almox:
        condicoes.append("p.codigo ILIKE %s")
        params.append(f"%{cod_almox}%")
    if cod_produto:
        condicoes.append("p.produto::text ILIKE %s")
        params.append(f"%{cod_produto}%")
    if nome_produto:
        condicoes.append("p.nome ILIKE %s")
        params.append(f"%{nome_produto}%")
    if lote:
        condicoes.append(
            "EXISTS (SELECT 1 FROM public.lote lt WHERE lt.produto = p.produto AND lt.lotefornecedor ILIKE %s)"
        )
        params.append(f"%{lote}%")
    if usuario_logado:
        condicoes.append(
            f"""EXISTS (
                SELECT 1 FROM public.lote lt2
                JOIN public.estoque e2 ON e2.lote = lt2.lote
                WHERE lt2.produto = p.produto AND e2.armazem IN ({SQL_ARMAZENS_DO_USUARIO})
            )"""
        )
        params.append(usuario_logado)

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    base_from = f"""
        FROM public.produto p
        LEFT JOIN public.classe c ON p.classe = c.classe
        LEFT JOIN public.subgrupo sg ON c.subgrupo = sg.subgrupo
        LEFT JOIN public.unidadeproduto up ON p.unidadeproduto = up.unidadeproduto
        {where}
    """

    tamanho_pagina = 20
    offset = (pagina - 1) * tamanho_pagina

    try:
        total = run_query(f"SELECT count(*) AS total {base_from}", params)[0]["total"]

        sql_dados = f"""
            SELECT
                p.codigoreferencia AS cod_seplag,
                p.codigo AS cod_almox,
                p.produto AS cod_produto,
                p.nome AS nome_produto,
                c.descricao AS classe,
                sg.descricao AS sub_grupo,
                up.sigla AS apresentacao,
                p.referenciasus AS procedimento_sus
            {base_from}
            ORDER BY p.produto
            LIMIT %s OFFSET %s
        """
        dados = run_query(sql_dados, params + [tamanho_pagina, offset])
        return jsonify(
            {
                "dados": dados,
                "total": total,
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            }
        )
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/produtos_lotes")
def api_produtos_lotes():
    # lotes de um produto (com dados do fornecedor), carregado so quando o usuario clica na linha
    # se o filtro de lote da tela principal estiver ativo, so traz o(s) lote(s) que batem
    produto = request.args.get("produto")
    lote = request.args.get("lote")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    if not produto:
        return jsonify([])

    condicoes = ["l.produto = %s"]
    params = [produto]

    if lote:
        condicoes.append("l.lotefornecedor ILIKE %s")
        params.append(f"%{lote}%")
    if usuario_logado:
        condicoes.append(
            f"""EXISTS (
                SELECT 1 FROM public.estoque e2
                WHERE e2.lote = l.lote AND e2.armazem IN ({SQL_ARMAZENS_DO_USUARIO})
            )"""
        )
        params.append(usuario_logado)

    where = " AND ".join(condicoes)

    sql = f"""
        SELECT
            l.lote AS lote_id,
            pj_forn.cnpj AS cnpj,
            pes_forn.nome AS fornecedor,
            pj_forn.nomefantasia AS nome_fantasia,
            l.lotefornecedor AS lote,
            to_char(l.validade, 'DD-MM-YY') AS validade
        FROM public.lote l
        LEFT JOIN public.fornecedor forn ON l.fornecedor = forn.fornecedor
        LEFT JOIN public.pessoa pes_forn ON forn.pessoa = pes_forn.pessoa
        LEFT JOIN public.pessoajuridica pj_forn ON pj_forn.pessoa = forn.pessoa
        WHERE {where}
        ORDER BY l.validade
    """
    return _consulta_generica(sql, params)


@app.route("/api/produtos_notas")
def api_produtos_notas():
    # nao ha FK direta lote->nota, entao seguimos a cadeia de movimentacao:
    # lote -> estoque -> entradaitem -> entradacabecalho, e casamos com notacabecalho
    # batendo pessoa (via fornecedor) + notafiscal + serienota
    lote_id = request.args.get("lote")
    if not lote_id:
        return jsonify([])

    sql = """
        SELECT DISTINCT
            nc.notafiscal AS numero_nota,
            nc.serienota AS serie,
            to_char(nc.emissaonota, 'DD-MM-YY') AS data_emissao,
            nc.observacao AS observacao,
            nc.emissaonota AS ordenacao
        FROM public.estoque e
        JOIN public.entradaitem ei ON ei.estoque = e.estoque
        JOIN public.entradacabecalho ec ON ec.entradacabecalho = ei.entradacabecalho
        JOIN public.fornecedor forn ON forn.pessoa = ec.pessoa
        JOIN public.notacabecalho nc
            ON nc.fornecedor = forn.fornecedor
           AND nc.notafiscal = ec.notafiscal
           AND nc.serienota = ec.serienota
        WHERE e.lote = %s
        ORDER BY ordenacao DESC
    """
    return _consulta_generica(sql, [lote_id])


@app.route("/api/vencidos")
def api_vencidos():
    # igual ao /api/estoque, mas so lista produto com lote vencido (validade < hoje) e estoque > 0
    cod_seplag = request.args.get("cod_seplag")
    cod_almox = request.args.get("cod_almox")
    cod_produto = request.args.get("cod_produto")
    nome_produto = request.args.get("nome_produto")
    lote = request.args.get("lote")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    try:
        pagina = max(int(request.args.get("pagina", 1)), 1)
    except ValueError:
        pagina = 1

    condicoes = []
    params = []

    if cod_seplag:
        condicoes.append("p.codigoreferencia ILIKE %s")
        params.append(f"%{cod_seplag}%")
    if cod_almox:
        condicoes.append("p.codigo ILIKE %s")
        params.append(f"%{cod_almox}%")
    if cod_produto:
        condicoes.append("p.produto::text ILIKE %s")
        params.append(f"%{cod_produto}%")
    if nome_produto:
        condicoes.append("p.nome ILIKE %s")
        params.append(f"%{nome_produto}%")
    if lote:
        condicoes.append(
            "EXISTS (SELECT 1 FROM public.lote lt WHERE lt.produto = p.produto AND lt.lotefornecedor ILIKE %s)"
        )
        params.append(f"%{lote}%")

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    # filtro de armazem do usuario logado vem antes na string SQL (dentro da subquery), entao o
    # parametro dele precisa ir antes dos outros na lista - por isso um params_completo separado
    filtro_armazem_usuario = f"AND e.armazem IN ({SQL_ARMAZENS_DO_USUARIO})" if usuario_logado else ""
    params_completo = ([usuario_logado] if usuario_logado else []) + params

    base_from = f"""
        FROM public.produto p
        JOIN (
            SELECT lt.produto, SUM(e.quantidade) AS total
            FROM public.lote lt
            JOIN public.estoque e ON e.lote = lt.lote
            JOIN public.armazem arm_e ON arm_e.armazem = e.armazem
            WHERE lt.validade < CURRENT_DATE
              AND arm_e.tipoarmazem = 'C'
            {filtro_armazem_usuario}
            GROUP BY lt.produto
            HAVING SUM(e.quantidade) > 0
        ) venc ON venc.produto = p.produto
        LEFT JOIN public.classe c ON p.classe = c.classe
        LEFT JOIN public.subgrupo sg ON c.subgrupo = sg.subgrupo
        LEFT JOIN public.unidadeproduto up ON p.unidadeproduto = up.unidadeproduto
        {where}
    """

    tamanho_pagina = 20
    offset = (pagina - 1) * tamanho_pagina

    try:
        total = run_query(f"SELECT count(*) AS total {base_from}", params_completo)[0]["total"]

        sql_dados = f"""
            SELECT
                p.codigoreferencia AS cod_seplag,
                p.codigo AS cod_almox,
                p.produto AS cod_produto,
                p.nome AS nome_produto,
                c.descricao AS classe,
                sg.descricao AS sub_grupo,
                up.sigla AS apresentacao,
                p.referenciasus AS procedimento_sus,
                venc.total AS total_estoque
            {base_from}
            ORDER BY p.produto
            LIMIT %s OFFSET %s
        """
        dados = run_query(sql_dados, params_completo + [tamanho_pagina, offset])
        return jsonify(
            {
                "dados": dados,
                "total": total,
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            }
        )
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/vencidos_lotes")
def api_vencidos_lotes():
    # so lotes vencidos (validade < hoje) e com estoque > 0, do que vence ha mais tempo pro mais recente
    produto = request.args.get("produto")
    lote = request.args.get("lote")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    if not produto:
        return jsonify([])

    condicoes = ["l.produto = %s", "l.validade < CURRENT_DATE"]
    params = [produto]

    if lote:
        condicoes.append("l.lotefornecedor ILIKE %s")
        params.append(f"%{lote}%")

    where = " AND ".join(condicoes)

    # o filtro de armazem fica dentro da subquery eq, que aparece antes do WHERE de fora no
    # texto do SQL - por isso os parametros dela vao primeiro na lista
    filtro_armazem_usuario = f"AND e.armazem IN ({SQL_ARMAZENS_DO_USUARIO})" if usuario_logado else ""
    params_completo = ([usuario_logado] if usuario_logado else []) + params

    sql = f"""
        SELECT
            l.lote AS lote_id,
            pj_forn.cnpj AS cnpj,
            pes_forn.nome AS fornecedor,
            pj_forn.nomefantasia AS nome_fantasia,
            l.lotefornecedor AS lote,
            to_char(l.validade, 'DD-MM-YY') AS validade,
            eq.quantidade AS quantidade
        FROM public.lote l
        LEFT JOIN public.fornecedor forn ON l.fornecedor = forn.fornecedor
        LEFT JOIN public.pessoa pes_forn ON forn.pessoa = pes_forn.pessoa
        LEFT JOIN public.pessoajuridica pj_forn ON pj_forn.pessoa = forn.pessoa
        JOIN (
            SELECT e.lote, SUM(e.quantidade) AS quantidade
            FROM public.estoque e
            JOIN public.armazem arm_e ON arm_e.armazem = e.armazem
            WHERE arm_e.tipoarmazem = 'C'
            {filtro_armazem_usuario}
            GROUP BY e.lote
            HAVING SUM(e.quantidade) > 0
        ) eq ON eq.lote = l.lote
        WHERE {where}
        ORDER BY l.validade ASC
    """
    return _consulta_generica(sql, params_completo)


@app.route("/api/estoque")
def api_estoque():
    # mesmos filtros da tela de produtos, mas so lista quem tem estoque > 0 (soma de todos os lotes)
    cod_seplag = request.args.get("cod_seplag")
    cod_almox = request.args.get("cod_almox")
    cod_produto = request.args.get("cod_produto")
    nome_produto = request.args.get("nome_produto")
    lote = request.args.get("lote")
    subgrupo = request.args.get("subgrupo")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    try:
        pagina = max(int(request.args.get("pagina", 1)), 1)
    except ValueError:
        pagina = 1

    condicoes = []
    params = []

    if cod_seplag:
        condicoes.append("p.codigoreferencia ILIKE %s")
        params.append(f"%{cod_seplag}%")
    if cod_almox:
        condicoes.append("p.codigo ILIKE %s")
        params.append(f"%{cod_almox}%")
    if cod_produto:
        condicoes.append("p.produto::text ILIKE %s")
        params.append(f"%{cod_produto}%")
    if nome_produto:
        condicoes.append("p.nome ILIKE %s")
        params.append(f"%{nome_produto}%")
    if lote:
        condicoes.append(
            "EXISTS (SELECT 1 FROM public.lote lt WHERE lt.produto = p.produto AND lt.lotefornecedor ILIKE %s)"
        )
        params.append(f"%{lote}%")
    if subgrupo:
        condicoes.append("sg.descricao ILIKE %s")
        params.append(f"%{subgrupo}%")

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    # filtro de armazem do usuario logado vem antes na string SQL (dentro da subquery), entao o
    # parametro dele precisa ir antes dos outros na lista - por isso um params_completo separado
    filtro_armazem_usuario = f"AND e.armazem IN ({SQL_ARMAZENS_DO_USUARIO})" if usuario_logado else ""
    params_completo = ([usuario_logado] if usuario_logado else []) + params

    base_from = f"""
        FROM public.produto p
        JOIN (
            SELECT lt.produto, SUM(e.quantidade) AS total
            FROM public.lote lt
            JOIN public.estoque e ON e.lote = lt.lote
            JOIN public.armazem arm_e ON arm_e.armazem = e.armazem
            WHERE arm_e.tipoarmazem = 'C'
            {filtro_armazem_usuario}
            GROUP BY lt.produto
            HAVING SUM(e.quantidade) > 0
        ) est ON est.produto = p.produto
        LEFT JOIN public.classe c ON p.classe = c.classe
        LEFT JOIN public.subgrupo sg ON c.subgrupo = sg.subgrupo
        LEFT JOIN public.unidadeproduto up ON p.unidadeproduto = up.unidadeproduto
        LEFT JOIN public.estoquetotal et ON et.produto = p.produto
        {where}
    """

    tamanho_pagina = 10
    offset = (pagina - 1) * tamanho_pagina

    try:
        # total e dados numa unica passada: o JOIN pesado (base_from) roda uma vez so, numa CTE
        # materializada, e tanto a contagem quanto a pagina saem dela - antes rodava o mesmo JOIN
        # duas vezes (uma so pra contar, outra pra paginar). total_geral vem de uma subquery
        # separada da pagina, pra continuar certo mesmo quando a pagina pedida vier vazia
        sql_dados = f"""
            WITH filtrado AS MATERIALIZED (
                SELECT
                    p.codigoreferencia AS cod_seplag,
                    p.codigo AS cod_almox,
                    p.produto AS cod_produto,
                    p.nome AS nome_produto,
                    c.descricao AS classe,
                    sg.descricao AS sub_grupo,
                    up.sigla AS apresentacao,
                    p.referenciasus AS procedimento_sus,
                    est.total AS total_estoque,
                    et.customedio AS custo_medio,
                    (est.total * et.customedio) AS valor_total
                {base_from}
            )
            SELECT
                (SELECT count(*) FROM filtrado) AS total_geral,
                COALESCE((
                    SELECT json_agg(pagina.* ORDER BY pagina.cod_produto)
                    FROM (SELECT * FROM filtrado ORDER BY cod_produto LIMIT %s OFFSET %s) pagina
                ), '[]'::json) AS dados_json
        """
        resultado = run_query(sql_dados, params_completo + [tamanho_pagina, offset])[0]
        return jsonify(
            {
                "dados": resultado["dados_json"],
                "total": resultado["total_geral"],
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            }
        )
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/estoque_lotes")
def api_estoque_lotes():
    # lotes+quantidade de um produto, carregado so quando o usuario clica na linha
    # ordenado do lote que vence primeiro pro que vence por ultimo
    produto = request.args.get("produto")
    lote = request.args.get("lote")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    if not produto:
        return jsonify([])

    condicoes = ["l.produto = %s"]
    params = [produto]

    if lote:
        condicoes.append("l.lotefornecedor ILIKE %s")
        params.append(f"%{lote}%")

    where = " AND ".join(condicoes)

    # o filtro de armazem fica dentro da subquery eq, que aparece antes do WHERE de fora no
    # texto do SQL - por isso os parametros dela vao primeiro na lista
    filtro_armazem_usuario = f"AND e.armazem IN ({SQL_ARMAZENS_DO_USUARIO})" if usuario_logado else ""
    params_completo = ([usuario_logado] if usuario_logado else []) + params

    sql = f"""
        SELECT
            l.lote AS lote_id,
            pj_forn.cnpj AS cnpj,
            pes_forn.nome AS fornecedor,
            pj_forn.nomefantasia AS nome_fantasia,
            l.lotefornecedor AS lote,
            to_char(l.validade, 'DD-MM-YY') AS validade,
            eq.quantidade AS quantidade,
            et.customedio AS custo_medio,
            (eq.quantidade * et.customedio) AS valor_total
        FROM public.lote l
        LEFT JOIN public.fornecedor forn ON l.fornecedor = forn.fornecedor
        LEFT JOIN public.pessoa pes_forn ON forn.pessoa = pes_forn.pessoa
        LEFT JOIN public.pessoajuridica pj_forn ON pj_forn.pessoa = forn.pessoa
        LEFT JOIN public.estoquetotal et ON et.produto = l.produto
        JOIN (
            SELECT e.lote, SUM(e.quantidade) AS quantidade
            FROM public.estoque e
            JOIN public.armazem arm_e ON arm_e.armazem = e.armazem
            WHERE arm_e.tipoarmazem = 'C'
            {filtro_armazem_usuario}
            GROUP BY e.lote
            HAVING SUM(e.quantidade) > 0
        ) eq ON eq.lote = l.lote
        WHERE {where}
        ORDER BY l.validade ASC
    """
    return _consulta_generica(sql, params_completo)


@app.route("/api/estoque_unidades")
def api_estoque_unidades():
    # lotes+quantidade de um produto em CADA armazem, sem filtro de tipo nem de armazem do usuario
    # logado - "unidades" mostra o produto em TODOS os armazens, inclusive os que nao sao tipo C -
    # com a data da ultima saida daquele lote naquele armazem especifico (si.estoque correlaciona
    # pelo par lote+armazem)
    produto = request.args.get("produto")
    if not produto:
        return jsonify([])

    sql = """
        SELECT
            COALESCE(pes_arm.nome, arm.sigla) AS nome_armazem,
            l.lotefornecedor AS lote,
            to_char(l.validade, 'DD-MM-YY') AS validade,
            e.quantidade AS quantidade,
            ultima.data_ultima_saida
        FROM public.estoque e
        JOIN public.lote l ON l.lote = e.lote
        JOIN public.armazem arm ON arm.armazem = e.armazem
        LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
        LEFT JOIN LATERAL (
            SELECT to_char(MAX(sc.data), 'DD-MM-YY') AS data_ultima_saida
            FROM public.saidaitem si
            JOIN public.saidacabecalho sc ON sc.saidacabecalho = si.saidacabecalho
            WHERE si.estoque = e.estoque
        ) ultima ON TRUE
        WHERE l.produto = %s AND e.quantidade > 0
        ORDER BY nome_armazem, l.validade ASC
    """
    return _consulta_generica(sql, [produto])


@app.route("/api/estoque_contratos")
def api_estoque_contratos():
    # atas/contratos que tem esse produto - uma linha por pedidoitem, incluindo cada aditivo
    # separadamente (nao so o mais recente de cada familia), com o saldo (quantidade ainda nao
    # entregue) de cada linha. situacao=validos restringe as familias cujo aditivo mais recente
    # ainda esta vigente (datafim > hoje) - mesmo criterio de "valido" usado em /api/atas_contratos;
    # sem o parametro, traz validos e vencidos (usado em aquisicoes.html)
    produto = request.args.get("produto")
    situacao = request.args.get("situacao")
    if not produto:
        return jsonify([])

    condicoes = ["pi.produto = %s"]
    params = [produto]

    if situacao == "validos":
        condicoes.append("""
            EXISTS (
                SELECT 1 FROM public.pedidocabecalho pc_latest
                WHERE pc_latest.numeroidentificacao = pc.numeroidentificacao
                AND pc_latest.numeroaditivo = (
                    SELECT MAX(pc2.numeroaditivo) FROM public.pedidocabecalho pc2
                    WHERE pc2.numeroidentificacao = pc.numeroidentificacao
                )
                AND pc_latest.datafim > CURRENT_DATE
            )
        """)

    where = " AND ".join(condicoes)

    sql = f"""
        SELECT
            COALESCE(pc.numerocontrato, pc.numeroata) AS numero,
            CASE WHEN pc.atapreco = 'S' THEN 'Ata' ELSE 'Contrato' END AS tipo,
            pc.numeroaditivo AS aditivo,
            pj.cnpj AS cnpj,
            pes.nome AS fornecedor,
            pj.nomefantasia AS nome_fantasia,
            pi.quantidade AS quantidade_total,
            pi.valorunitario AS valor_unitario,
            (pi.quantidade - COALESCE(pi.quantidadeentregue, 0)) AS saldo,
            to_char(pc.datainicio, 'DD-MM-YY') AS data_inicio,
            to_char(pc.datafim, 'DD-MM-YY') AS data_fim
        FROM public.pedidoitem pi
        JOIN public.pedidocabecalho pc ON pc.pedidocabecalho = pi.pedidocabecalho
        JOIN public.fornecedor forn ON forn.fornecedor = pc.fornecedor
        JOIN public.pessoa pes ON pes.pessoa = forn.pessoa
        LEFT JOIN public.pessoajuridica pj ON pj.pessoa = forn.pessoa
        WHERE {where}
        ORDER BY pes.nome, pc.numeroidentificacao, pc.numeroaditivo
    """
    return _consulta_generica(sql, params)


@app.route("/api/estoque_movimentacoes")
def api_estoque_movimentacoes():
    # relatorio de entradas (entradaitem) e saidas (saidaitem) de um produto - entrada usa o custo
    # unitario dela mesma, saida usa o custo medio do produto (saida nao guarda preco proprio)
    produto = request.args.get("produto")
    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")
    if not produto:
        return jsonify({"erro": "produto obrigatorio"}), 400

    condicoes_entrada = ["lt.produto = %s"]
    params_entrada = [produto]
    condicoes_saida = ["lt.produto = %s"]
    params_saida = [produto]

    if data_inicio:
        condicoes_entrada.append("ei._creation >= %s")
        params_entrada.append(data_inicio)
        condicoes_saida.append("si._creation >= %s")
        params_saida.append(data_inicio)
    if data_fim:
        condicoes_entrada.append("ei._creation < (%s::date + INTERVAL '1 day')")
        params_entrada.append(data_fim)
        condicoes_saida.append("si._creation < (%s::date + INTERVAL '1 day')")
        params_saida.append(data_fim)

    sql = f"""
        SELECT nome_pessoa, tipo_movimentacao, lote, armazem, data, quantidade, valor_unitario, subtotal FROM (
            SELECT
                pes.nome AS nome_pessoa,
                tm.descricao AS tipo_movimentacao,
                lt.lotefornecedor AS lote,
                COALESCE(pes_arm.nome, arm.sigla) AS armazem,
                ei._creation AS data_ordenacao,
                to_char(ei._creation, 'DD-MM-YY HH24:MI') AS data,
                ei.quantidade AS quantidade,
                ei.custounitario AS valor_unitario,
                (ei.quantidade * ei.custounitario) AS subtotal
            FROM public.entradaitem ei
            JOIN public.entradacabecalho ec ON ec.entradacabecalho = ei.entradacabecalho
            JOIN public.estoque e ON e.estoque = ei.estoque
            JOIN public.lote lt ON lt.lote = e.lote
            LEFT JOIN public.pessoa pes ON pes.pessoa = ec.pessoa
            LEFT JOIN public.tipomovimentacao tm ON tm.tipomovimentacao = ec.tipomovimentacao
            LEFT JOIN public.armazem arm ON arm.armazem = ec.armazem
            LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
            WHERE {' AND '.join(condicoes_entrada)}

            UNION ALL

            SELECT
                pes.nome AS nome_pessoa,
                tm.descricao AS tipo_movimentacao,
                lt.lotefornecedor AS lote,
                COALESCE(pes_arm.nome, arm.sigla) AS armazem,
                si._creation AS data_ordenacao,
                to_char(si._creation, 'DD-MM-YY HH24:MI') AS data,
                (-si.quantidade) AS quantidade,
                et.customedio AS valor_unitario,
                (-si.quantidade * et.customedio) AS subtotal
            FROM public.saidaitem si
            JOIN public.saidacabecalho sc ON sc.saidacabecalho = si.saidacabecalho
            JOIN public.estoque e ON e.estoque = si.estoque
            JOIN public.lote lt ON lt.lote = e.lote
            LEFT JOIN public.pessoa pes ON pes.pessoa = sc.pessoa
            LEFT JOIN public.tipomovimentacao tm ON tm.tipomovimentacao = sc.tipomovimentacao
            LEFT JOIN public.estoquetotal et ON et.produto = lt.produto
            LEFT JOIN public.armazem arm ON arm.armazem = sc.armazem
            LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
            WHERE {' AND '.join(condicoes_saida)}
        ) mov
        ORDER BY data_ordenacao DESC
        LIMIT 3000
    """
    try:
        movimentacoes = run_query(sql, params_entrada + params_saida)
        estoque_atual = run_query(
            "SELECT quantidade, customedio FROM public.estoquetotal WHERE produto = %s", [produto]
        )
        return jsonify(
            {
                "movimentacoes": movimentacoes,
                "estoque_atual": estoque_atual[0] if estoque_atual else None,
            }
        )
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/estoque_abastecimento")
def api_estoque_abastecimento():
    # parametros de abastecimento (minimo, seguranca, ponto de ressuprimento) por armazem - so
    # armazem tipo C (almoxarifado/consumo), mesmo filtro usado no resto da tela de estoque
    # estoqueminimo = estoque ideal pra 60 dias, estoqueseguranca pra 90, pontoressuprimento pra
    # 180 - (estoqueminimo/60) eh o consumo diario implicito, autonomia_dias = quanto tempo o
    # estoque atual aguenta nesse ritmo
    produto = request.args.get("produto")
    if not produto:
        return jsonify([])

    sql = """
        SELECT
            COALESCE(pes.nome, arm.sigla) AS nome_armazem,
            ea.quantidade AS total_estoque,
            ea.estoqueminimo AS estoque_minimo,
            ea.estoqueseguranca AS estoque_seguranca,
            ea.pontoressuprimento AS ponto_ressuprimento,
            CASE
                WHEN ea.estoqueminimo > 0 THEN ROUND((ea.quantidade * 60) / ea.estoqueminimo, 1)
                ELSE NULL
            END AS autonomia_dias
        FROM public.estoquearmazem ea
        JOIN public.armazem arm ON arm.armazem = ea.armazem
        LEFT JOIN public.pessoa pes ON pes.pessoa = arm.pessoa
        WHERE ea.produto = %s AND arm.tipoarmazem = 'C'
        ORDER BY nome_armazem
    """
    # saldo em contrato = quanto ainda falta entregar (quantidade - quantidadeentregue) somado de
    # todo pedidoitem desse produto, so contando familias (numeroidentificacao) ainda validas hoje
    # (datafim do aditivo mais recente > hoje) - mesma nocao de "valido" usada em atas_contratos
    sql_saldo_contrato = """
        SELECT COALESCE(SUM(pi.quantidade - COALESCE(pi.quantidadeentregue, 0)), 0) AS saldo_contrato
        FROM public.pedidoitem pi
        JOIN public.pedidocabecalho pc ON pc.pedidocabecalho = pi.pedidocabecalho
        WHERE pi.produto = %s
        AND EXISTS (
            SELECT 1 FROM public.pedidocabecalho pc_latest
            WHERE pc_latest.numeroidentificacao = pc.numeroidentificacao
            AND pc_latest.numeroaditivo = (
                SELECT MAX(pc2.numeroaditivo) FROM public.pedidocabecalho pc2
                WHERE pc2.numeroidentificacao = pc.numeroidentificacao
            )
            AND pc_latest.datafim > CURRENT_DATE
        )
    """
    try:
        linhas = run_query(sql, [produto])
        saldo_contrato = run_query(sql_saldo_contrato, [produto])[0]["saldo_contrato"]

        for linha in linhas:
            total_disponivel = float(linha["total_estoque"]) + float(saldo_contrato)
            linha["saldo_contrato"] = saldo_contrato
            linha["minimo_ok"] = total_disponivel >= float(linha["estoque_minimo"])
            linha["seguranca_ok"] = total_disponivel >= float(linha["estoque_seguranca"])
            linha["ressuprimento_ok"] = total_disponivel >= float(linha["ponto_ressuprimento"])

        return jsonify(linhas)
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/aquisicoes")
def api_aquisicoes():
    # igual a /api/estoque (mesmos filtros, mesma paginacao), mas so lista produto que tem pelo
    # menos um armazem onde o ponto de ressuprimento ta configurado (> 0) e NAO esta sendo
    # atendido (estoque daquele armazem + saldo em contrato do produto < ponto de ressuprimento) -
    # mesma regra de "insuficiente" usada no sinalizador ⚠ de /api/estoque_abastecimento
    cod_seplag = request.args.get("cod_seplag")
    cod_almox = request.args.get("cod_almox")
    cod_produto = request.args.get("cod_produto")
    nome_produto = request.args.get("nome_produto")
    lote = request.args.get("lote")
    subgrupo = request.args.get("subgrupo")
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    try:
        pagina = max(int(request.args.get("pagina", 1)), 1)
    except ValueError:
        pagina = 1

    condicoes = []
    params = []

    if cod_seplag:
        condicoes.append("p.codigoreferencia ILIKE %s")
        params.append(f"%{cod_seplag}%")
    if cod_almox:
        condicoes.append("p.codigo ILIKE %s")
        params.append(f"%{cod_almox}%")
    if cod_produto:
        condicoes.append("p.produto::text ILIKE %s")
        params.append(f"%{cod_produto}%")
    if nome_produto:
        condicoes.append("p.nome ILIKE %s")
        params.append(f"%{nome_produto}%")
    if lote:
        condicoes.append(
            "EXISTS (SELECT 1 FROM public.lote lt WHERE lt.produto = p.produto AND lt.lotefornecedor ILIKE %s)"
        )
        params.append(f"%{lote}%")
    if subgrupo:
        condicoes.append("sg.descricao ILIKE %s")
        params.append(f"%{subgrupo}%")

    # ponto de ressuprimento insuficiente, restrito aos mesmos armazens que o usuario enxerga
    filtro_armazem_ea = f"AND arm_ea.armazem IN ({SQL_ARMAZENS_DO_USUARIO})" if usuario_logado else ""
    condicoes.append(f"""
        EXISTS (
            SELECT 1
            FROM public.estoquearmazem ea
            JOIN public.armazem arm_ea ON arm_ea.armazem = ea.armazem
            LEFT JOIN saldo_por_produto sp ON sp.produto = ea.produto
            WHERE ea.produto = p.produto
            AND arm_ea.tipoarmazem = 'C'
            {filtro_armazem_ea}
            AND ea.pontoressuprimento > 0
            AND (ea.quantidade + COALESCE(sp.saldo, 0)) < ea.pontoressuprimento
        )
    """)

    where = f"WHERE {' AND '.join(condicoes)}"

    # filtro de armazem do usuario logado vem antes na string SQL (dentro da subquery), entao o
    # parametro dele precisa ir antes dos outros na lista - por isso um params_completo separado.
    # o parametro do filtro de armazem da condicao de ressuprimento vem DEPOIS dos filtros comuns
    # (ela fica por ultimo em condicoes), entao o parametro dela vai no final
    filtro_armazem_usuario = f"AND e.armazem IN ({SQL_ARMAZENS_DO_USUARIO})" if usuario_logado else ""
    params_completo = ([usuario_logado] if usuario_logado else []) + params + ([usuario_logado] if usuario_logado else [])

    base_from = f"""
        FROM public.produto p
        JOIN (
            SELECT lt.produto, SUM(e.quantidade) AS total
            FROM public.lote lt
            JOIN public.estoque e ON e.lote = lt.lote
            JOIN public.armazem arm_e ON arm_e.armazem = e.armazem
            WHERE arm_e.tipoarmazem = 'C'
            {filtro_armazem_usuario}
            GROUP BY lt.produto
            HAVING SUM(e.quantidade) > 0
        ) est ON est.produto = p.produto
        LEFT JOIN public.classe c ON p.classe = c.classe
        LEFT JOIN public.subgrupo sg ON c.subgrupo = sg.subgrupo
        LEFT JOIN public.unidadeproduto up ON p.unidadeproduto = up.unidadeproduto
        LEFT JOIN public.estoquetotal et ON et.produto = p.produto
        {where}
    """

    tamanho_pagina = 10
    offset = (pagina - 1) * tamanho_pagina

    try:
        sql_dados = f"""
            WITH saldo_por_produto AS MATERIALIZED (
                SELECT pi.produto, COALESCE(SUM(pi.quantidade - COALESCE(pi.quantidadeentregue, 0)), 0) AS saldo
                FROM public.pedidoitem pi
                JOIN public.pedidocabecalho pc ON pc.pedidocabecalho = pi.pedidocabecalho
                WHERE EXISTS (
                    SELECT 1 FROM public.pedidocabecalho pc_latest
                    WHERE pc_latest.numeroidentificacao = pc.numeroidentificacao
                    AND pc_latest.numeroaditivo = (
                        SELECT MAX(pc2.numeroaditivo) FROM public.pedidocabecalho pc2
                        WHERE pc2.numeroidentificacao = pc.numeroidentificacao
                    )
                    AND pc_latest.datafim > CURRENT_DATE
                )
                GROUP BY pi.produto
            ),
            filtrado AS MATERIALIZED (
                SELECT
                    p.codigoreferencia AS cod_seplag,
                    p.codigo AS cod_almox,
                    p.produto AS cod_produto,
                    p.nome AS nome_produto,
                    c.descricao AS classe,
                    sg.descricao AS sub_grupo,
                    up.sigla AS apresentacao,
                    p.referenciasus AS procedimento_sus,
                    est.total AS total_estoque,
                    et.customedio AS custo_medio,
                    (est.total * et.customedio) AS valor_total
                {base_from}
            )
            SELECT
                (SELECT count(*) FROM filtrado) AS total_geral,
                COALESCE((
                    SELECT json_agg(pagina.* ORDER BY pagina.cod_produto)
                    FROM (SELECT * FROM filtrado ORDER BY cod_produto LIMIT %s OFFSET %s) pagina
                ), '[]'::json) AS dados_json
        """
        resultado = run_query(sql_dados, params_completo + [tamanho_pagina, offset])[0]
        return jsonify(
            {
                "dados": resultado["dados_json"],
                "total": resultado["total_geral"],
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            }
        )
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


def _contagem_em_andamento(tipomov, usuario_logado, armazem=None):
    # quantos pedidos estao reivindicados e AINDA em andamento (_creation = _update) pra essa
    # etapa (separacao ou distribuicao) - conta em cima de armazemmovimentacao (tabela pequena),
    # so junta com saidacabecalho pra aplicar o filtro de armazem/status
    condicoes = ["sc.status <> 'E'", f"am.tipomovimentacao = {tipomov}", "am._creation = am._update"]
    params = []
    join_armazem = ""
    if armazem:
        join_armazem = """
            LEFT JOIN public.armazem arm ON arm.armazem = sc.armazem
            LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
        """
        condicoes.append("pes_arm.nome = %s")
        params.append(armazem)
    if usuario_logado:
        condicoes.append(f"sc.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)
    where = f"WHERE {' AND '.join(condicoes)}"
    sql = f"""
        SELECT count(DISTINCT am.saidacabecalho) AS total
        FROM sist_logistica.armazemmovimentacao am
        JOIN public.saidacabecalho sc ON sc.saidacabecalho = am.saidacabecalho
        {join_armazem}
        {where}
    """
    return run_query(sql, params)[0]["total"]


@app.route("/api/painel_contadores")
def api_painel_contadores():
    # os 5 numeros dos cards do painel de chamada - mesmo filtro de data/armazem que cada tela de
    # origem usa, so trocando a lista inteira por um count(*) (fica leve pro painel dar poll)
    data_inicio = request.args.get("data_inicio") or "2026-09-01"
    usuario_logado_raw = request.args.get("usuario_logado")
    usuario_logado = _usuario_para_filtro_armazem(usuario_logado_raw)
    # selecao manual de armazem (dropdown do painel, so aparece pra admin/sem-login) - prevalece
    # sobre o armazem implicito do usuario logado
    armazem = request.args.get("armazem")

    # novos pedidos: requisicao ainda nao tocada por nenhuma saida (mesma condicao de
    # /api/pedidos_novos, incluindo o SET LOCAL que forca nested loop - ver comentario la)
    condicoes_novos = [
        "rq.data >= %s",
        """NOT EXISTS (
            SELECT 1 FROM public.requisicaoitem ri
            WHERE ri.requisicao = rq.requisicao
            AND EXISTS (SELECT 1 FROM public.saidaitem si WHERE si.requisicaoitem = ri.requisicaoitem)
        )""",
    ]
    params_novos = [data_inicio]
    join_novos = ""
    if armazem:
        join_novos = """
            LEFT JOIN public.armazem arm ON arm.armazem = rq.armazem
            LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
        """
        condicoes_novos.append("pes_arm.nome = %s")
        params_novos.append(armazem)
    if usuario_logado:
        condicoes_novos.append(f"rq.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params_novos.append(usuario_logado)
    sql_novos = f"""
        SET LOCAL enable_hashjoin = off;
        SET LOCAL enable_mergejoin = off;
        SELECT count(*) AS total FROM public.requisicao rq {join_novos} WHERE {' AND '.join(condicoes_novos)}
    """
    novos = run_query(sql_novos, params_novos)[0]["total"]

    a_separar = _consulta_pedidos(data_inicio=data_inicio, armazem=armazem, usuario_logado=usuario_logado_raw, apenas_contagem=True)
    para_distribuicao = _consulta_pedidos(
        data_inicio=data_inicio,
        armazem=armazem,
        usuario_logado=usuario_logado_raw,
        condicoes_base=["sc.status <> 'E'", SQL_SEPARACAO_CONCLUIDA, f"NOT {SQL_DISTRIBUICAO_RECLAMADA}"],
        apenas_contagem=True,
    )
    em_separacao = _contagem_em_andamento(TIPOMOV_SEPARACAO, usuario_logado, armazem)
    em_distribuicao = _contagem_em_andamento(TIPOMOV_DISTRIBUICAO, usuario_logado, armazem)

    return jsonify({
        "novos": novos,
        "a_separar": a_separar,
        "em_separacao": em_separacao,
        "para_distribuicao": para_distribuicao,
        "em_distribuicao": em_distribuicao,
    })


@app.route("/api/painel_chamados")
def api_painel_chamados():
    # "chamados" = mudancas de etapa ja registradas em armazemmovimentacao (inicio/fim de
    # separacao e de distribuicao) - novos pedidos e pedidos a separar ainda nao tem linha nessa
    # tabela, entao so entram no painel de chamada quando alguem reivindica pra separacao
    usuario_logado = _usuario_para_filtro_armazem(request.args.get("usuario_logado"))
    armazem = request.args.get("armazem")
    try:
        limite = max(int(request.args.get("limite", 5)), 1)
    except ValueError:
        limite = 5

    join_armazem = ""
    condicoes_extra = []
    params = []
    if armazem:
        join_armazem = """
            LEFT JOIN public.armazem arm ON arm.armazem = sc.armazem
            LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
        """
        condicoes_extra.append("pes_arm.nome = %s")
        params.append(armazem)
    if usuario_logado:
        condicoes_extra.append(f"sc.armazem IN ({SQL_ARMAZENS_DO_USUARIO})")
        params.append(usuario_logado)
    filtro_armazem = ("AND " + " AND ".join(condicoes_extra)) if condicoes_extra else ""
    params.append(limite)

    sql = f"""
        SELECT sc.saidacabecalho AS numero_pedido, pes.nome AS requisitante, eventos.momento, eventos.etapa
        FROM (
            SELECT DISTINCT saidacabecalho, _creation AS momento, 'Separação Iniciada' AS etapa
            FROM sist_logistica.armazemmovimentacao WHERE tipomovimentacao = {TIPOMOV_SEPARACAO}
            UNION ALL
            SELECT DISTINCT saidacabecalho, _update AS momento, 'Separação Concluída' AS etapa
            FROM sist_logistica.armazemmovimentacao WHERE tipomovimentacao = {TIPOMOV_SEPARACAO} AND _creation <> _update
            UNION ALL
            SELECT DISTINCT saidacabecalho, _creation AS momento, 'Distribuição Iniciada' AS etapa
            FROM sist_logistica.armazemmovimentacao WHERE tipomovimentacao = {TIPOMOV_DISTRIBUICAO}
            UNION ALL
            SELECT DISTINCT saidacabecalho, _update AS momento, 'Distribuição Concluída' AS etapa
            FROM sist_logistica.armazemmovimentacao WHERE tipomovimentacao = {TIPOMOV_DISTRIBUICAO} AND _creation <> _update
        ) eventos
        JOIN public.saidacabecalho sc ON sc.saidacabecalho = eventos.saidacabecalho
        LEFT JOIN public.pessoa pes ON pes.pessoa = sc.pessoa
        {join_armazem}
        WHERE sc.status <> 'E' {filtro_armazem}
        ORDER BY eventos.momento DESC
        LIMIT %s
    """
    linhas = run_query(sql, params)
    for linha in linhas:
        momento = linha.pop("momento")
        linha["data_chamada"] = momento.strftime("%d/%m/%y")
        linha["hora_chamada"] = momento.strftime("%H:%M:%S")
    return jsonify(linhas)


@app.route("/api/pagamentos")
def api_pagamentos():
    # TODO homem: cola consulta real aqui
    return _consulta_generica("SELECT 1 AS placeholder LIMIT 0")


@app.route("/api/atas_contratos")
def api_atas_contratos():
    # TODO homem: status/modalidade ainda nao tem mapeamento definido (statuspedido/modalidadelicitacao
    # sao codigos de 1 letra e nao sei o que cada valor significa) - filtros ficam guardados mas sem uso
    numero_ata = request.args.get("numero_ata")
    numero_contrato = request.args.get("numero_contrato")
    cnpj = request.args.get("cnpj")
    fornecedor = request.args.get("fornecedor")
    produto = request.args.get("produto")
    filtro_data_inicio = request.args.get("data_inicio")
    filtro_data_fim = request.args.get("data_fim")
    situacao = request.args.get("situacao")  # "validos" ou "vencidos"
    tipo = request.args.get("tipo")  # "ata" (atapreco = 'S') ou "contrato" (atapreco = 'N')
    try:
        pagina = max(int(request.args.get("pagina", 1)), 1)
    except ValueError:
        pagina = 1

    # so a linha base (numeroaditivo = 0) representa uma ata/contrato na listagem -
    # os aditivos aparecem por fora, sob demanda, em /api/atas_contratos_aditivos
    condicoes = ["pc.numeroaditivo = 0"]
    params = []

    if numero_ata:
        condicoes.append("pc.numeroata ILIKE %s")
        params.append(f"%{numero_ata}%")
    if numero_contrato:
        condicoes.append("pc.numerocontrato ILIKE %s")
        params.append(f"%{numero_contrato}%")
    if cnpj:
        # tira mascara (pontos, barra, traco) - o campo no banco eh so digito
        cnpj_digitos = re.sub(r"\D", "", cnpj)
        condicoes.append("pj.cnpj ILIKE %s")
        params.append(f"%{cnpj_digitos}%")
    if fornecedor:
        condicoes.append("pes.nome ILIKE %s")
        params.append(f"%{fornecedor}%")
    if produto:
        condicoes.append("""
            EXISTS (
                SELECT 1 FROM public.pedidoitem pi
                JOIN public.produto p ON p.produto = pi.produto
                WHERE pi.pedidocabecalho = pc.pedidocabecalho AND p.nome ILIKE %s
            )
        """)
        params.append(f"%{produto}%")
    # filtro de periodo: traz contratos cuja data de inicio E data fim (efetiva, maior aditivo)
    # caem dentro do intervalo informado - os dois extremos do contrato "cabem" no filtro
    if filtro_data_inicio and filtro_data_fim:
        condicoes.append("pc.datainicio BETWEEN %s AND %s")
        condicoes.append("ult.efetivo BETWEEN %s AND %s")
        params.extend([filtro_data_inicio, filtro_data_fim, filtro_data_inicio, filtro_data_fim])
    elif filtro_data_inicio:
        condicoes.append("pc.datainicio >= %s AND ult.efetivo >= %s")
        params.extend([filtro_data_inicio, filtro_data_inicio])
    elif filtro_data_fim:
        condicoes.append("pc.datainicio <= %s AND ult.efetivo <= %s")
        params.extend([filtro_data_fim, filtro_data_fim])
    # prazo = data fim efetiva (maior aditivo) - hoje: validos cobre prazo >= 0 (ainda vigente hoje,
    # inclusive quem vence hoje), vencido so quando prazo < 0 (data fim antes de hoje)
    if situacao == "validos":
        condicoes.append("ult.efetivo >= CURRENT_DATE")
    elif situacao == "vencidos":
        condicoes.append("ult.efetivo < CURRENT_DATE")
    # atapreco = 'S' quer dizer que o pedido eh uma ata (de registro de preco) - uma ata pode gerar
    # contrato (atapreco = 'N') usando so parte do saldo dela, por isso os dois viram secoes separadas
    if tipo == "ata":
        condicoes.append("pc.atapreco = 'S'")
    elif tipo == "contrato":
        condicoes.append("pc.atapreco = 'N'")

    where = f"WHERE {' AND '.join(condicoes)}"

    base_from = f"""
        FROM public.pedidocabecalho pc
        JOIN public.fornecedor forn ON forn.fornecedor = pc.fornecedor
        JOIN public.pessoa pes ON pes.pessoa = forn.pessoa
        LEFT JOIN public.pessoajuridica pj ON pj.pessoa = forn.pessoa
        LEFT JOIN LATERAL (
            SELECT
                pc2.datafim AS efetivo,
                (
                    SELECT SUM(pc3.totalpedido) FROM public.pedidocabecalho pc3
                    WHERE pc3.numeroidentificacao = pc.numeroidentificacao
                ) AS valor_total,
                (
                    SELECT SUM(pi.quantidadeentregue * pi.valorunitario)
                    FROM public.pedidoitem pi
                    JOIN public.pedidocabecalho pc4 ON pc4.pedidocabecalho = pi.pedidocabecalho
                    WHERE pc4.numeroidentificacao = pc.numeroidentificacao
                ) AS saldo_utilizado
            FROM public.pedidocabecalho pc2
            WHERE pc2.numeroidentificacao = pc.numeroidentificacao
            ORDER BY pc2.numeroaditivo DESC
            LIMIT 1
        ) ult ON TRUE
        {where}
    """

    tamanho_pagina = 10
    offset = (pagina - 1) * tamanho_pagina

    # validos: prazo do menor pro maior (vence antes primeiro). vencidos: data de vencimento do
    # mais atual (venceu a pouco tempo) pro mais antigo. sem situacao: ordem antiga (datainicio)
    if situacao == "validos":
        ordenacao = "ult.efetivo ASC NULLS LAST"
    elif situacao == "vencidos":
        ordenacao = "ult.efetivo DESC NULLS LAST"
    else:
        ordenacao = "pc.datainicio DESC NULLS LAST"

    try:
        total = run_query(f"SELECT count(*) AS total {base_from}", params)[0]["total"]

        sql_dados = f"""
            SELECT
                pc.pedidocabecalho AS pedidocabecalho,
                pc.numeroidentificacao AS numeroidentificacao,
                pj.cnpj AS cnpj,
                pes.nome AS fornecedor,
                pj.nomefantasia AS nome_fantasia,
                pc.numeroata AS num_ata,
                pc.numerocontrato AS num_contrato,
                to_char(pc.datainicio, 'DD-MM-YY') AS data_inicio,
                to_char(ult.efetivo, 'DD-MM-YY') AS data_fim,
                CASE
                    WHEN ult.efetivo >= CURRENT_DATE THEN (ult.efetivo - CURRENT_DATE)::text
                    ELSE 'Vencido'
                END AS prazo,
                ult.valor_total AS saldo_total,
                COALESCE(ult.saldo_utilizado, 0) AS saldo_utilizado,
                GREATEST(0, ult.valor_total - COALESCE(ult.saldo_utilizado, 0)) AS saldo_remanescente,
                CASE
                    WHEN COALESCE(ult.saldo_utilizado, 0) = 0 THEN 100
                    ELSE ROUND((ult.valor_total / ult.saldo_utilizado) * 100, 2)
                END AS percentual_utilizado,
                CASE
                    WHEN ult.valor_total > 0
                    THEN GREATEST(0, ROUND(((ult.valor_total - COALESCE(ult.saldo_utilizado, 0)) / ult.valor_total) * 100, 2))
                    ELSE 0
                END AS percentual_remanescente
            {base_from}
            ORDER BY {ordenacao}
            LIMIT %s OFFSET %s
        """
        dados = run_query(sql_dados, params + [tamanho_pagina, offset])
        return jsonify(
            {
                "dados": dados,
                "total": total,
                "pagina": pagina,
                "tamanho_pagina": tamanho_pagina,
            }
        )
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/atas_contratos_aditivos")
def api_atas_contratos_aditivos():
    # historico completo (base + aditivos) de uma ata/contrato, agrupado por numeroidentificacao
    identificacao = request.args.get("identificacao")
    if not identificacao:
        return jsonify([])

    sql = """
        SELECT
            pc.numeroaditivo AS numero_aditivo,
            pc.numeroata AS num_ata,
            pc.numerocontrato AS num_contrato,
            to_char(pc.datainicio, 'DD-MM-YY') AS data_inicio,
            to_char(pc.datafim, 'DD-MM-YY') AS data_fim
        FROM public.pedidocabecalho pc
        WHERE pc.numeroidentificacao = %s
        ORDER BY pc.numeroaditivo ASC
    """
    return _consulta_generica(sql, [identificacao])


@app.route("/api/atas_contratos_itens")
def api_atas_contratos_itens():
    # itens de uma ata/contrato especifica (join direto por pedidocabecalho, igual a tela de produtos pro nome)
    pedidocabecalho = request.args.get("pedidocabecalho")
    if not pedidocabecalho:
        return jsonify([])

    sql = """
        SELECT
            p.nome AS nome_produto,
            pi.quantidade AS quantidade,
            COALESCE(pi.quantidadeentregue, 0) AS quantidade_utilizada,
            pi.valorunitario AS valor_unitario,
            (pi.quantidade * pi.valorunitario) AS subtotal,
            (pi.quantidade - COALESCE(pi.quantidadeentregue, 0)) AS saldo_quantidade,
            ((pi.quantidade - COALESCE(pi.quantidadeentregue, 0)) * pi.valorunitario) AS saldo_valor,
            CASE
                WHEN pi.quantidade > 0
                THEN GREATEST(0, ROUND(((pi.quantidade - COALESCE(pi.quantidadeentregue, 0)) / pi.quantidade) * 100, 2))
                ELSE 0
            END AS percentual_remanescente
        FROM public.pedidoitem pi
        JOIN public.produto p ON p.produto = pi.produto
        WHERE pi.pedidocabecalho = %s
        ORDER BY pi.item
    """
    return _consulta_generica(sql, [pedidocabecalho])


# base compartilhada pelas telas de dashboard de atas/contratos - mesmo esqueleto (LATERAL com o
# aditivo mais recente da familia) usado em /api/atas_contratos, so que sem paginacao/filtro de tela
_DASHBOARD_BASE_FROM = """
    FROM public.pedidocabecalho pc
    JOIN public.fornecedor forn ON forn.fornecedor = pc.fornecedor
    JOIN public.pessoa pes ON pes.pessoa = forn.pessoa
    LEFT JOIN LATERAL (
        SELECT
            pc2.datafim AS efetivo,
            (
                SELECT SUM(pc3.totalpedido) FROM public.pedidocabecalho pc3
                WHERE pc3.numeroidentificacao = pc.numeroidentificacao
            ) AS valor_total,
            (
                SELECT SUM(pi.quantidadeentregue * pi.valorunitario)
                FROM public.pedidoitem pi
                JOIN public.pedidocabecalho pc4 ON pc4.pedidocabecalho = pi.pedidocabecalho
                WHERE pc4.numeroidentificacao = pc.numeroidentificacao
            ) AS saldo_utilizado
        FROM public.pedidocabecalho pc2
        WHERE pc2.numeroidentificacao = pc.numeroidentificacao
        ORDER BY pc2.numeroaditivo DESC
        LIMIT 1
    ) ult ON TRUE
    WHERE pc.numeroaditivo = 0
"""

# formula do percentual remanescente identica a de /api/atas_contratos (mesma logica da barra de saldo)
_DASHBOARD_PERCENTUAL_REMANESCENTE = """
    CASE
        WHEN ult.valor_total > 0
        THEN GREATEST(0, ROUND(((ult.valor_total - COALESCE(ult.saldo_utilizado, 0)) / ult.valor_total) * 100, 2))
        ELSE 0
    END
"""


def _dashboard_top5(situacao_cond, atapreco, filtro_saldo, ordenacao, limite=5):
    percentual = _DASHBOARD_PERCENTUAL_REMANESCENTE
    sql = f"""
        SELECT
            pes.nome AS fornecedor,
            pc.numeroata AS num_ata,
            pc.numerocontrato AS num_contrato,
            to_char(pc.datainicio, 'DD-MM-YY') AS data_inicio,
            to_char(ult.efetivo, 'DD-MM-YY') AS data_fim,
            ult.valor_total AS saldo_total,
            COALESCE(ult.saldo_utilizado, 0) AS saldo_utilizado,
            GREATEST(0, ult.valor_total - COALESCE(ult.saldo_utilizado, 0)) AS saldo_remanescente,
            {percentual} AS percentual_remanescente
        {_DASHBOARD_BASE_FROM}
        AND {situacao_cond}
        AND pc.atapreco = %s
        {filtro_saldo}
        ORDER BY {ordenacao}
        LIMIT {int(limite)}
    """
    return run_query(sql, [atapreco])


_NOMES_MES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
_CHAVES_BUCKET = ["cem_por_cento", "acima_50", "acima_30", "acima_10", "zero_por_cento"]


def _ultimos_6_meses():
    # 6 meses cheios (calendario), terminando no mes atual - usado pra alinhar os rotulos das barras
    hoje = datetime.date.today()
    ano, mes = hoje.year, hoje.month
    meses = []
    for _ in range(6):
        meses.append((ano, mes))
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
    meses.reverse()
    return [{"chave": f"{ano:04d}-{mes:02d}", "rotulo": f"{_NOMES_MES_PT[mes - 1]}/{str(ano)[2:]}"} for ano, mes in meses]


def _dashboard_vencidos_por_mes():
    # atas/contratos vencidos, mes a mes (dos ultimos 6 meses cheios), cada mes dividido pelo
    # percentual de saldo remanescente - vira as barras empilhadas do lado do grafico de pizza
    percentual = _DASHBOARD_PERCENTUAL_REMANESCENTE
    meses = _ultimos_6_meses()
    inicio = meses[0]["chave"] + "-01"

    sql = f"""
        SELECT
            to_char(date_trunc('month', ult.efetivo), 'YYYY-MM') AS mes,
            pc.atapreco AS atapreco,
            count(*) FILTER (WHERE {percentual} = 100) AS cem_por_cento,
            count(*) FILTER (WHERE {percentual} > 50 AND {percentual} < 100) AS acima_50,
            count(*) FILTER (WHERE {percentual} > 30 AND {percentual} <= 50) AS acima_30,
            count(*) FILTER (WHERE {percentual} > 10 AND {percentual} <= 30) AS acima_10,
            count(*) FILTER (WHERE {percentual} <= 10) AS zero_por_cento
        {_DASHBOARD_BASE_FROM}
        AND ult.efetivo IS NOT NULL AND ult.efetivo <= CURRENT_DATE AND ult.efetivo >= %s
        AND pc.atapreco IN ('S', 'N')
        GROUP BY date_trunc('month', ult.efetivo), pc.atapreco
    """
    linhas = run_query(sql, [inicio])
    por_chave = {(linha["mes"], linha["atapreco"]): linha for linha in linhas}

    def _serie(atapreco):
        return [
            {chave: (por_chave.get((mes["chave"], atapreco)) or {}).get(chave, 0) for chave in _CHAVES_BUCKET}
            for mes in meses
        ]

    return {"rotulos": [mes["rotulo"] for mes in meses], "atas": _serie("S"), "contratos": _serie("N")}


def _dashboard_validos_matriz_dias():
    # matriz pros validos: cada linha e um pedaco de percentual de utilizacao (igual a legenda do grafico
    # de pizza), cada coluna quantos dias faltam pra vencer - ajuda a achar quem ta gastando tudo e
    # vencendo logo (prioridade de renovacao) x quem ainda tem tempo/saldo sobrando
    percentual = _DASHBOARD_PERCENTUAL_REMANESCENTE
    dias = "(ult.efetivo - CURRENT_DATE)"
    sql = f"""
        SELECT
            CASE
                WHEN {percentual} = 100 THEN 'cem_por_cento'
                WHEN {percentual} > 50 THEN 'acima_50'
                WHEN {percentual} > 30 THEN 'acima_30'
                WHEN {percentual} > 10 THEN 'acima_10'
                ELSE 'zero_por_cento'
            END AS bucket_percentual,
            count(*) FILTER (WHERE {dias} <= 30) AS dias_30,
            count(*) FILTER (WHERE {dias} > 30 AND {dias} <= 90) AS dias_90,
            count(*) FILTER (WHERE {dias} > 90 AND {dias} <= 180) AS dias_180,
            count(*) FILTER (WHERE {dias} > 180) AS dias_mais
        {_DASHBOARD_BASE_FROM}
        AND ult.efetivo > CURRENT_DATE
        GROUP BY bucket_percentual
    """
    linhas = run_query(sql)
    por_bucket = {linha["bucket_percentual"]: linha for linha in linhas}
    colunas = ["dias_30", "dias_90", "dias_180", "dias_mais"]
    return {chave: {coluna: (por_bucket.get(chave) or {}).get(coluna, 0) for coluna in colunas} for chave in _CHAVES_BUCKET}


def _dashboard_atas_contratos(situacao):
    percentual = _DASHBOARD_PERCENTUAL_REMANESCENTE
    if situacao == "vencidos":
        # so os que venceram nos ultimos 6 meses - vencido sem data (NULL) nao entra, nao da pra saber quando venceu
        situacao_cond = "(ult.efetivo IS NOT NULL AND ult.efetivo <= CURRENT_DATE AND ult.efetivo >= CURRENT_DATE - INTERVAL '6 months')"
    else:
        situacao_cond = "ult.efetivo > CURRENT_DATE"

    def _buckets(filtro_tipo=""):
        sql_buckets = f"""
            SELECT
                count(*) FILTER (WHERE {percentual} = 100) AS cem_por_cento,
                count(*) FILTER (WHERE {percentual} > 50 AND {percentual} < 100) AS acima_50,
                count(*) FILTER (WHERE {percentual} > 30 AND {percentual} <= 50) AS acima_30,
                count(*) FILTER (WHERE {percentual} > 10 AND {percentual} <= 30) AS acima_10,
                count(*) FILTER (WHERE {percentual} <= 10) AS zero_por_cento
            {_DASHBOARD_BASE_FROM}
            AND {situacao_cond}
            {filtro_tipo}
        """
        return run_query(sql_buckets)[0]

    buckets = _buckets()
    # mes a mes so faz sentido pros vencidos (venceu QUANDO) - usado nas barras do lado do grafico de pizza
    por_mes = _dashboard_vencidos_por_mes() if situacao == "vencidos" else None
    # matriz de dias a vencer so faz sentido pros validos (ainda tem prazo pela frente)
    matriz_dias = _dashboard_validos_matriz_dias() if situacao == "validos" else None

    if situacao == "vencidos":
        # maior saldo remanescente primeiro (nao saldo total) - top 10 em vez de top 5, a tela
        # mostra so 5 de cada vez e rola sozinha pelo resto
        filtro_saldo = ""
        ordenacao = "saldo_remanescente DESC NULLS LAST"
        limite = 10
    else:
        # valido com saldo zerado = ja gastou tudo mas ainda ta na validade - risco de faltar
        # produto. maior prazo pra vencer primeiro (mais tempo rodando sem saldo = mais urgente
        # resolver) - top 10 em vez de top 5, a tela mostra so 5 de cada vez e rola sozinha
        filtro_saldo = f"AND {percentual} <= 0"
        ordenacao = "ult.efetivo DESC NULLS LAST"
        limite = 10

    contratos = _dashboard_top5(situacao_cond, "N", filtro_saldo, ordenacao, limite)
    atas = _dashboard_top5(situacao_cond, "S", filtro_saldo, ordenacao, limite)

    return {
        "buckets": buckets,
        "por_mes": por_mes,
        "matriz_dias": matriz_dias,
        "contratos": contratos,
        "atas": atas,
    }


@app.route("/api/dashboard_estoque_armazem")
def api_dashboard_estoque_armazem():
    # valor em estoque = quantidade (por armazem, tabela estoque) * customedio (custo medio do
    # produto, tabela estoquetotal) - customedio eh mais confiavel que o custo de um lote isolado,
    # que pode estar desatualizado/errado se aquele lote em particular teve preco fora da curva
    sql = """
        SELECT
            arm.armazem AS armazem,
            COALESCE(pes.nome, arm.sigla) AS nome_armazem,
            SUM(e.quantidade * et.customedio) AS valor
        FROM public.estoque e
        JOIN public.lote lt ON lt.lote = e.lote
        JOIN public.estoquetotal et ON et.produto = lt.produto
        JOIN public.armazem arm ON arm.armazem = e.armazem
        LEFT JOIN public.pessoa pes ON pes.pessoa = arm.pessoa
        WHERE arm.tipoarmazem = 'C' AND e.quantidade > 0
        GROUP BY arm.armazem, COALESCE(pes.nome, arm.sigla)
        HAVING SUM(e.quantidade * et.customedio) > 0
        ORDER BY valor DESC
    """
    try:
        dados = run_query(sql)
        valor_total = sum(float(linha["valor"]) for linha in dados) or 1
        for linha in dados:
            linha["percentual"] = round(float(linha["valor"]) / valor_total * 100, 2)
        return jsonify({"dados": dados, "valor_total": valor_total})
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


ARMAZENS_COBERTURA_PONTO_RESSUPRIMENTO = [74714, 194597, 49083881, 228756, 74712]


@app.route("/api/dashboard_ponto_ressuprimento")
def api_dashboard_ponto_ressuprimento():
    # por armazem (lista fixa definida em ARMAZENS_COBERTURA_PONTO_RESSUPRIMENTO): dos itens
    # que tem estoque (quantidade > 0), quantos tem ponto de ressuprimento configurado (> 0)
    # e quantos nao tem (= 0 ou nulo) - parametro vem de estoquearmazem, a mesma tabela usada
    # em /api/estoque_abastecimento
    sql = """
        SELECT
            COALESCE(pes.nome, arm.sigla) AS nome_armazem,
            count(*) FILTER (WHERE ea.quantidade > 0) AS total_itens,
            count(*) FILTER (WHERE ea.quantidade > 0 AND COALESCE(ea.pontoressuprimento, 0) = 0) AS sem_ponto,
            count(*) FILTER (WHERE ea.quantidade > 0 AND COALESCE(ea.pontoressuprimento, 0) > 0) AS com_ponto
        FROM public.armazem arm
        LEFT JOIN public.estoquearmazem ea ON ea.armazem = arm.armazem
        LEFT JOIN public.pessoa pes ON pes.pessoa = arm.pessoa
        WHERE arm.armazem = ANY(%s)
        GROUP BY arm.armazem, COALESCE(pes.nome, arm.sigla)
        ORDER BY nome_armazem
    """
    try:
        dados = run_query(sql, [ARMAZENS_COBERTURA_PONTO_RESSUPRIMENTO])
        for linha in dados:
            total = int(linha["total_itens"] or 0) or 1
            linha["percentual_sem"] = round(int(linha["sem_ponto"] or 0) / total * 100, 1)
            linha["percentual_com"] = round(int(linha["com_ponto"] or 0) / total * 100, 1)
        return jsonify(dados)
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/dashboard_itens_ponto_ressuprimento")
def api_dashboard_itens_ponto_ressuprimento():
    # ultimos 20 itens que atingiram o ponto de ressuprimento (estoque atual <= ponto), do mais
    # recente pro mais antigo - "data" vem de estoquearmazem._update, que muda toda vez que a
    # quantidade/parametro daquele produto+armazem e recalculado (ou seja, a cada movimentacao).
    # a tela mostra so 10 de cada vez e rola sozinha pelo resto. armazem (opcional) restringe a um
    # unico armazem pelo nome - usado no gauge do almoxarifado central
    armazem = request.args.get("armazem")
    condicoes = ["arm.tipoarmazem = 'C'", "ea.pontoressuprimento > 0", "ea.quantidade <= ea.pontoressuprimento"]
    params = []
    if armazem:
        condicoes.append("pes_arm.nome = %s")
        params.append(armazem)
    where = " AND ".join(condicoes)

    sql = f"""
        SELECT
            p.nome AS nome_produto,
            COALESCE(pes_arm.nome, arm.sigla) AS nome_armazem,
            ea.quantidade AS quantidade_atual,
            ea.pontoressuprimento AS ponto_ressuprimento,
            to_char(ea._update, 'DD/MM/YY') AS data
        FROM public.estoquearmazem ea
        JOIN public.armazem arm ON arm.armazem = ea.armazem
        LEFT JOIN public.pessoa pes_arm ON pes_arm.pessoa = arm.pessoa
        JOIN public.produto p ON p.produto = ea.produto
        WHERE {where}
        ORDER BY ea._update DESC
        LIMIT 20
    """
    return _consulta_generica(sql, params)


@app.route("/api/dashboard_gauge_ponto_ressuprimento")
def api_dashboard_gauge_ponto_ressuprimento():
    # gauge por armazem: dos itens com ponto de ressuprimento configurado, quantos estao com
    # estoque suficiente (acima do ponto) - meta fixa de 80%. um gauge por armazem tipo C (ver
    # /api/armazens pra lista completa), armazem default fica o almoxarifado central
    nome_armazem = request.args.get("armazem") or "ALMOXARIFADO CENTRAL"
    sql = """
        SELECT
            count(*) FILTER (WHERE ea.pontoressuprimento > 0) AS total_com_ponto,
            count(*) FILTER (WHERE ea.pontoressuprimento > 0 AND ea.quantidade > ea.pontoressuprimento) AS suficientes
        FROM public.estoquearmazem ea
        JOIN public.armazem arm ON arm.armazem = ea.armazem
        LEFT JOIN public.pessoa pes ON pes.pessoa = arm.pessoa
        WHERE arm.tipoarmazem = 'C' AND pes.nome = %s AND ea.quantidade > 0
    """
    try:
        linha = run_query(sql, [nome_armazem])[0]
        total = int(linha["total_com_ponto"])
        suficientes = int(linha["suficientes"])
        percentual = round(suficientes / total * 100, 1) if total else 0
        return jsonify({
            "nome_armazem": nome_armazem,
            "total_com_ponto": total,
            "suficientes": suficientes,
            "percentual": percentual,
            "meta": 80,
        })
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/dashboard_atas_contratos_vencidos")
def api_dashboard_atas_contratos_vencidos():
    try:
        return jsonify(_dashboard_atas_contratos("vencidos"))
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


@app.route("/api/dashboard_atas_contratos_validos")
def api_dashboard_atas_contratos_validos():
    try:
        return jsonify(_dashboard_atas_contratos("validos"))
    except Exception as erro:
        return jsonify({"erro": str(erro)}), 500


if __name__ == "__main__":
    # fogo aceso, sistema roda
    app.run(host="0.0.0.0", debug=True, port=5000)
