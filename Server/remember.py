from Server.postgre_insert import insert_record
from Server.vector_db_insert import add_vector

# remember.py
def remember(
    raw_content: str,
    summary: str,
    table: str,
    record: dict,
):
    if table == "memories":
        record["content"] = raw_content
    elif table == "chat_history":
        record["message"] = raw_content
    elif table == "user_facts":
        record["fact_value"] = raw_content
    elif table == "tasks":
        record["description"] = raw_content
    elif table == "reminders":
        record["description"] = raw_content

    postgres_id = insert_record(
        table=table,
        record=record,
    )

    metadata = {
        "table": table,
        "postgres_id": postgres_id,
    }

    add_vector(
        memory_id=postgres_id,
        summary=summary,
        metadata=metadata,
    )

    return postgres_id