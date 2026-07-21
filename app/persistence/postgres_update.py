import psycopg
from psycopg.rows import dict_row
from app.core.debug import postgres_connection
from app.core.database import postgres_config

DB_CONFIG = postgres_config()


def get_connection():
    return postgres_connection(DB_CONFIG, row_factory=dict_row)


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
