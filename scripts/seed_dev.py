"""Cria o schema e povoa o banco local 'almoxarifado_dev' com dados ficticios.

So mexe no banco de teste (nunca no de producao). Roda de novo sempre
que precisar resetar os dados: apaga e recria as tabelas do zero.

Uso: python3 scripts/seed_dev.py
"""
import os
import random
from datetime import datetime, timedelta

import psycopg2

# senha so pelo ambiente (DB_PASSWORD) - nunca no codigo
DB_CONFIG_DEV = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME_DEV", "almoxarifado_dev"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
}

ARMAZENS = [
    "ALMOXARIFADO CENTRAL",
    "ALMOXARIFADO MEDICO",
    "FARMACIA SATELITE CENTRO CIRURGICO",
    "CENTRAL DE ABASTECIMENTO FARMACEUTICO",
    "LABORATORIO",
]

SETORES = [
    "UTI CARDIO PULMONAR",
    "UTI SEMI INTENSIVA",
    "PRONTO SOCORRO ADULTO",
    "PEDIATRIA",
    "CENTRO CIRURGICO",
    "AMBULATORIO",
    "MANUTENCAO",
    "NUTRICAO",
]

NOMES_USUARIO = [
    ("joaosilva", "Joao da Silva"),
    ("mariasouza", "Maria Souza"),
    ("carlosoliveira", "Carlos Oliveira"),
    ("anapereira", "Ana Pereira"),
]

DDL = """
DROP TABLE IF EXISTS public.requisicao;
DROP TABLE IF EXISTS public.requisitante;
DROP TABLE IF EXISTS public.armazem;
DROP TABLE IF EXISTS public.usuario;
DROP TABLE IF EXISTS public.pessoa;

CREATE TABLE public.pessoa (
    pessoa NUMERIC PRIMARY KEY,
    nome VARCHAR(80) NOT NULL
);

CREATE TABLE public.usuario (
    usuario NUMERIC PRIMARY KEY,
    identificacao VARCHAR(20) NOT NULL,
    nome VARCHAR(40) NOT NULL,
    senha VARCHAR(20) NOT NULL,
    sha CHAR(64),
    tipo CHAR(1) NOT NULL,
    status CHAR(1) NOT NULL,
    modo CHAR(1) NOT NULL,
    bloqueado CHAR(1),
    tentativas NUMERIC DEFAULT 0
);

CREATE TABLE public.armazem (
    armazem NUMERIC PRIMARY KEY,
    pessoa NUMERIC REFERENCES public.pessoa(pessoa),
    tipoarmazem CHAR(1) NOT NULL
);

CREATE TABLE public.requisitante (
    requisitante NUMERIC PRIMARY KEY,
    pessoa NUMERIC REFERENCES public.pessoa(pessoa)
);

CREATE TABLE public.requisicao (
    requisicao NUMERIC PRIMARY KEY,
    requisitante NUMERIC REFERENCES public.requisitante(requisitante),
    armazem NUMERIC REFERENCES public.armazem(armazem),
    data TIMESTAMP NOT NULL
);
"""


def seed():
    conn = psycopg2.connect(**DB_CONFIG_DEV)
    cur = conn.cursor()
    cur.execute(DDL)

    pessoa_id = 1

    # armazens (viram pessoa + armazem, tipo 'C' pra aparecer no filtro)
    ids_armazem = []
    for nome in ARMAZENS:
        cur.execute("INSERT INTO public.pessoa (pessoa, nome) VALUES (%s, %s)", (pessoa_id, nome))
        cur.execute(
            "INSERT INTO public.armazem (armazem, pessoa, tipoarmazem) VALUES (%s, %s, 'C')",
            (pessoa_id, pessoa_id),
        )
        ids_armazem.append(pessoa_id)
        pessoa_id += 1

    # setores/requisitantes
    ids_requisitante = []
    for nome in SETORES:
        cur.execute("INSERT INTO public.pessoa (pessoa, nome) VALUES (%s, %s)", (pessoa_id, nome))
        cur.execute(
            "INSERT INTO public.requisitante (requisitante, pessoa) VALUES (%s, %s)",
            (pessoa_id, pessoa_id),
        )
        ids_requisitante.append(pessoa_id)
        pessoa_id += 1

    # usuarios de teste (senha em texto puro, mesmo esquema simplificado do login atual)
    usuario_id = 1
    for identificacao, nome in NOMES_USUARIO:
        cur.execute(
            """
            INSERT INTO public.usuario (usuario, identificacao, nome, senha, tipo, status, modo, bloqueado, tentativas)
            VALUES (%s, %s, %s, '1234', '2', '1', '1', 'N', 0)
            """,
            (usuario_id, identificacao, nome),
        )
        usuario_id += 1
    cur.execute(
        """
        INSERT INTO public.usuario (usuario, identificacao, nome, senha, tipo, status, modo, bloqueado, tentativas)
        VALUES (%s, 'admin', 'Administrador (teste)', 'admin', '1', '1', '1', 'N', 0)
        """,
        (usuario_id,),
    )

    # requisicoes ficticias espalhadas nos ultimos 5 dias, incluindo hoje
    requisicao_id = 51700000
    agora = datetime.now()
    for dias_atras in range(5):
        dia = agora - timedelta(days=dias_atras)
        qtd = random.randint(6, 12)
        for _ in range(qtd):
            hora = dia.replace(
                hour=random.randint(7, 18),
                minute=random.randint(0, 59),
                second=0,
                microsecond=0,
            )
            cur.execute(
                """
                INSERT INTO public.requisicao (requisicao, requisitante, armazem, data)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    requisicao_id,
                    random.choice(ids_requisitante),
                    random.choice(ids_armazem),
                    hora,
                ),
            )
            requisicao_id += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"pronto: {len(ARMAZENS)} armazens, {len(SETORES)} setores, {requisicao_id - 51700000} requisicoes, {usuario_id} usuarios (inclui admin/admin)")


if __name__ == "__main__":
    seed()
