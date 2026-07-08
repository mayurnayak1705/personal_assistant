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
    return psycopg.connect(
        **DB_CONFIG,
        row_factory=dict_row,
    )


def update_record(
    table: str,
    record_id: str,
    record: dict,
):
    """
    Updates a PostgreSQL record.
    """

    columns = []
    values = []

    for key, value in record.items():
        columns.append(f"{key}=%s")
        values.append(value)

    values.append(record_id)

    query = f"""
        UPDATE {table}
        SET {', '.join(columns)},
            updated_at = NOW()
        WHERE id = %s
    """
    print(query)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, values)
            conn.commit()

    return record_id