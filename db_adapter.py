
import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("Defina a variável de ambiente DATABASE_URL (Postgres)")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def q(sql: str):
    return sql.replace("?", "%s") if "?" in sql else sql
