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


def fetch_records(search_results):
    ids = search_results["ids"][0]
    metadatas = search_results["metadatas"][0]
    output = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            for memory_id, metadata in zip(ids, metadatas):
                table = metadata["table"]
                cur.execute(
                    f"""
                    SELECT *
                    FROM {table}
                    WHERE id=%s
                    """,
                    (memory_id,),
                )
                row = cur.fetchone()
                if row:
                    row["table"] = table
                    output.append(row)
    return output