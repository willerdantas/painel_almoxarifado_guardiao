"""Homem cava buraco ate o banco postgres."""
import json
import os

import psycopg2
import psycopg2.extras

# conexao padrao: variaveis de ambiente DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD. senha
# nunca no codigo - sem DB_PASSWORD (e sem db_config.json) a conexao falha e o login oferece o
# usuario de teste pra configurar pela tela Configuração do Banco
_CONFIG_PADRAO = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "isivitaedb_hm"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

# se existir db_config.json (criado pela tela Configuração do Banco ao editar a conexao), usa ele
# no lugar do padrao acima. fica fora do git (.gitignore) porque guarda a senha
_CAMINHO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_config.json")

if os.path.exists(_CAMINHO_CONFIG):
    with open(_CAMINHO_CONFIG) as _arquivo:
        DB_CONFIG = json.load(_arquivo)
else:
    DB_CONFIG = dict(_CONFIG_PADRAO)


def salvar_config(novo_config):
    # atualiza o dict EXISTENTE (em vez de trocar por um objeto novo) pra quem importou
    # "DB_CONFIG" de outro modulo (ex.: app.py) enxergar a mudanca sem precisar reimportar.
    # arquivo so legivel pelo dono (tem a senha do banco)
    DB_CONFIG.update(novo_config)
    with open(os.open(_CAMINHO_CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as arquivo:
        json.dump(DB_CONFIG, arquivo, indent=2)
    os.chmod(_CAMINHO_CONFIG, 0o600)


def get_conn():
    # abre porta pra caverna dos dados
    return psycopg2.connect(**DB_CONFIG)


def run_query(sql, params=None):
    # manda flecha, traz resultado
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            # description vem preenchido tanto em SELECT quanto em INSERT/UPDATE ... RETURNING -
            # nos dois casos tem linha pra buscar, mas so no segundo precisa comitar (senao a
            # conexao fecha e desfaz a escrita antes de alguem ler o commit)
            if cur.description:
                resultado = cur.fetchall()
                conn.commit()
                return resultado
            conn.commit()
            return []
    finally:
        conn.close()
