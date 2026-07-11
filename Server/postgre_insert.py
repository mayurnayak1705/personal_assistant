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


def insert_chat_history_batch(conversation_id: str, user_id: str, turns: list[dict]) -> list[str]:
    """
    Batch-inserts one conversation's worth of chat turns into chat_history
    in a single transaction. Called once, when a session ends.

    Each item in `turns` must have: role, message, token_count, and
    optionally created_at (falls back to CURRENT_TIMESTAMP if omitted).

    Returns the list of inserted row UUIDs (same order as `turns`).
    """
    if not turns:
        return []

    inserted_ids = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            for turn in turns:
                cur.execute(
                    """
                    INSERT INTO chat_history
                        (conversation_id, user_id, role, message, token_count, created_at)
                    VALUES (%s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP))
                    RETURNING id;
                    """,
                    (
                        conversation_id,
                        user_id,
                        turn["role"],
                        turn["message"],
                        turn.get("token_count"),
                        turn.get("created_at"),
                    ),
                )
                inserted_ids.append(str(cur.fetchone()["id"]))
            conn.commit()

    return inserted_ids