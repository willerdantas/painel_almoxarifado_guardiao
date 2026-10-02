"""Homem cava buraco ate o banco postgres."""
import json
import os

import psycopg2
import psycopg2.extras

# banco de TESTE com dado ficticio (scripts/seed_dev.py cria e povoa)
# pra voltar pro banco real, troca dbname de volta pra "isivitaedb_hm"
_CONFIG_PADRAO = {
    "host": "localhost",
    "port": 30433,
    "dbname": "isivitaedb_hm",
    "user": "postgres",
    "password": "grandeviagem",
}

# se existir db_config.json (criado pela tela Configuração do Banco ao editar a conexao), usa ele
# no lugar do padrao acima - fica fora do db.py pra dar pra editar sem reescrever codigo python
_CAMINHO_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_config.json")

if os.path.exists(_CAMINHO_CONFIG):
    with open(_CAMINHO_CONFIG) as _arquivo:
        DB_CONFIG = json.load(_arquivo)
else:
    DB_CONFIG = dict(_CONFIG_PADRAO)


def salvar_config(novo_config):
    # atualiza o dict EXISTENTE (em vez de trocar por um objeto novo) pra quem importou
    # "DB_CONFIG" de outro modulo (ex.: app.py) enxergar a mudanca sem precisar reimportar
    DB_CONFIG.update(novo_config)
    with open(_CAMINHO_CONFIG, "w") as arquivo:
        json.dump(DB_CONFIG, arquivo, indent=2)


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
