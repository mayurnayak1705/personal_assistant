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


def fetch_conversation_history(conversation_id: str, limit: int = 50) -> list[dict]:
    """
    Returns the turns already persisted for a conversation_id, oldest first.

    Used by routes.py as a fallback when the in-memory session buffer is
    empty — e.g. the server restarted mid-conversation, or the session was
    already flushed once and the same conversation_id is continuing.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, message, token_count, created_at
                FROM chat_history
                WHERE conversation_id = %s
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (conversation_id, limit),
            )
            return cur.fetchall()
        

def fetch_user_facts() -> str:
    """
    Returns all user facts as a single formatted string.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fact_value
                FROM user_facts
                ORDER BY created_at ASC
            """)

            rows = cur.fetchall()

    if not rows:
        return "No user facts found."

    return "\n".join(
        f"- {row['fact_value']}"
        for row in rows
    )