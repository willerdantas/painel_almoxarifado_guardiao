"""Homem cava buraco ate o banco postgres."""
import psycopg2
import psycopg2.extras

# banco de TESTE com dado ficticio (scripts/seed_dev.py cria e povoa)
# pra voltar pro banco real, troca dbname de volta pra "isivitaedb_hm"
DB_CONFIG = {
    "host": "localhost",
    "port": 30433,
    "dbname": "isivitaedb_hm",
    "user": "postgres",
    "password": "grandeviagem",
}


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
