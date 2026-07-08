from Server.postgre_update import update_record
from Server.vector_db_update import update_vector


def update(
    postgres_id: str,
    table: str,
    raw_content: str,
    summary: str,
    record: dict,
):
    """
    Update an existing record in PostgreSQL and Chroma.
    """

    # Put the raw content into the correct PostgreSQL column
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

    # Update PostgreSQL
    update_record(
        table=table,
        record_id=postgres_id,
        record=record,
    )

    # Update vector DB
    metadata = {
        "table": table,
        "postgres_id": postgres_id,
    }

    update_vector(
        memory_id=postgres_id,
        summary=summary,
        metadata=metadata,
    )

    return {
        "status": "updated",
        "postgres_id": postgres_id,
        "table": table,
    }