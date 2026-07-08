import psycopg
from psycopg.rows import dict_row

DB_CONFIG = {
    "host": "localhost",
    "dbname": "ai_assistant_memory",
    "user": "postgres",
    "password": "mayur",
    "port": 5432,
}


def get_connection():
    return psycopg.connect(**DB_CONFIG, row_factory=dict_row)


def insert_record(table: str, record: dict):
    """
    Generic insert into any table.
    Returns inserted UUID.
    """

    columns = list(record.keys())
    values = list(record.values())

    placeholders = ",".join(["%s"] * len(values))
    column_string = ",".join(columns)

    query = f"""
        INSERT INTO {table}
        ({column_string})
        VALUES ({placeholders})
        RETURNING id;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, values)
            record_id = cur.fetchone()["id"]
            conn.commit()

    return str(record_id)