import re

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


NAME_FACT_KEYS = ("name", "first_name", "full_name", "preferred_name")


def _normalize_profile_name(value: str) -> str:
    """Convert stored natural-language facts such as 'My name is Mayur' into a name."""
    cleaned = str(value or "").strip().strip(".!,")
    match = re.match(
        r"^(?:my name is|i am|i'm|call me)\s+(.+)$",
        cleaned,
        flags=re.IGNORECASE,
    )
    return (match.group(1) if match else cleaned).strip().strip(".!,")


def fetch_user_profile_name(user_id: str) -> dict | None:
    """Fetch the best name fact for this user, with a single-user DB fallback."""
    order = "confidence DESC NULLS LAST, updated_at DESC NULLS LAST, created_at DESC"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT user_id, fact_key, fact_value
                FROM user_facts
                WHERE user_id = %s AND LOWER(fact_key) = ANY(%s)
                ORDER BY {order}
                LIMIT 1;
                """,
                (user_id, list(NAME_FACT_KEYS)),
            )
            row = cur.fetchone()
            if row is None:
                # This application currently has one configured person but
                # older memories used IDs such as "user-1" while tools use
                # "mayur". Fall back only when exactly one name-owner exists.
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (user_id) user_id, fact_key, fact_value
                    FROM user_facts
                    WHERE LOWER(fact_key) = ANY(%s)
                    ORDER BY user_id, {order};
                    """,
                    (list(NAME_FACT_KEYS),),
                )
                candidates = cur.fetchall()
                row = candidates[0] if len(candidates) == 1 else None
    if row is None:
        return None
    display_name = _normalize_profile_name(row["fact_value"])
    if not display_name:
        return None
    return {
        "user_id": row["user_id"],
        "display_name": display_name,
        "first_name": display_name.split()[0],
        "fact_key": row["fact_key"],
    }
