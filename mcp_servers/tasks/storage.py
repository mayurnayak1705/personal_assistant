"""PostgreSQL persistence for the Tasks MCP server."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.persistence.postgres_insert import get_connection


TASK_FIELDS = (
    "id",
    "user_id",
    "project_id",
    "title",
    "description",
    "priority",
    "status",
    "due_date",
    "completed_at",
    "created_at",
    "updated_at",
    "category",
    "source",
    "recurrence",
)


def init_task_schema() -> None:
    """Create task storage and add optional columns to older task tables."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR NOT NULL,
                    project_id UUID,
                    title VARCHAR NOT NULL,
                    description TEXT,
                    priority VARCHAR DEFAULT 'normal',
                    status VARCHAR DEFAULT 'todo',
                    due_date TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS category VARCHAR;
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'chat';
                ALTER TABLE tasks ADD COLUMN IF NOT EXISTS recurrence VARCHAR;
                CREATE TABLE IF NOT EXISTS task_action_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR NOT NULL,
                    task_id UUID NOT NULL,
                    action VARCHAR NOT NULL,
                    before_state JSONB,
                    after_state JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_user_status_due
                    ON tasks(user_id, status, due_date);
                CREATE INDEX IF NOT EXISTS idx_task_history_user_created
                    ON task_action_history(user_id, created_at DESC);
                """
            )
            conn.commit()


def _json_ready(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        key: (
            value.isoformat()
            if isinstance(value, datetime)
            else str(value)
            if isinstance(value, UUID)
            else value
        )
        for key, value in record.items()
    }


def _fetch_task(cur, *, task_id: str, user_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT id, user_id, project_id, title, description, priority, status,
               due_date, completed_at, created_at, updated_at,
               category, source, recurrence
        FROM tasks
        WHERE id = %s AND user_id = %s;
        """,
        (task_id, user_id),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _record_action(
    cur,
    *,
    user_id: str,
    task_id: str,
    action: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    cur.execute(
        """
        INSERT INTO task_action_history
            (user_id, task_id, action, before_state, after_state)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (
            user_id,
            task_id,
            action,
            Jsonb(_json_ready(before)) if before is not None else None,
            Jsonb(_json_ready(after)) if after is not None else None,
        ),
    )


def create_task_record(
    *,
    user_id: str,
    title: str,
    description: str,
    priority: str,
    due_date: datetime | None,
    category: str | None,
    recurrence: str | None,
    source: str,
) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasks
                    (user_id, title, description, priority, status, due_date,
                     category, recurrence, source)
                VALUES (%s, %s, %s, %s, 'todo', %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    user_id,
                    title,
                    description,
                    priority,
                    due_date,
                    category,
                    recurrence,
                    source,
                ),
            )
            task_id = str(cur.fetchone()["id"])
            task = _fetch_task(cur, task_id=task_id, user_id=user_id)
            assert task is not None
            _record_action(
                cur,
                user_id=user_id,
                task_id=task_id,
                action="create",
                before=None,
                after=task,
            )
            conn.commit()
            return task


def list_task_records(
    *,
    user_id: str,
    view: str,
    now: datetime,
    query: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conditions = ["user_id = %s"]
    params: list[Any] = [user_id]

    if view == "open":
        conditions.append("status IN ('todo', 'in_progress')")
    elif view in {"due", "overdue"}:
        conditions.extend(["status IN ('todo', 'in_progress')", "due_date <= %s"])
        params.append(now)
    elif view == "today":
        conditions.extend(
            [
                "status IN ('todo', 'in_progress')",
                "due_date >= date_trunc('day', %s::timestamp)",
                "due_date < date_trunc('day', %s::timestamp) + interval '1 day'",
            ]
        )
        params.extend([now, now])
    elif view == "upcoming":
        conditions.extend(["status IN ('todo', 'in_progress')", "due_date > %s"])
        params.append(now)
    elif view == "completed":
        conditions.append("status = 'completed'")
    elif view == "cancelled":
        conditions.append("status = 'cancelled'")
    elif view != "all":
        raise ValueError("view must be open, due, overdue, today, upcoming, completed, cancelled, or all")

    if query:
        conditions.append("(title ILIKE %s OR description ILIKE %s)")
        params.extend([f"%{query}%", f"%{query}%"])
    if priority:
        conditions.append("LOWER(priority) = LOWER(%s)")
        params.append(priority)
    if category:
        conditions.append("LOWER(category) = LOWER(%s)")
        params.append(category)

    params.append(max(1, min(limit, 200)))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, user_id, project_id, title, description, priority, status,
                       due_date, completed_at, created_at, updated_at,
                       category, source, recurrence
                FROM tasks
                WHERE {' AND '.join(conditions)}
                ORDER BY
                    CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                    due_date ASC,
                    created_at DESC
                LIMIT %s;
                """,
                params,
            )
            return [dict(row) for row in cur.fetchall()]


def update_task_record(
    *,
    task_id: str,
    user_id: str,
    changes: dict[str, Any],
    action: str = "update",
) -> dict[str, Any] | None:
    if not changes:
        raise ValueError("At least one task field must be supplied")
    allowed = {
        "title",
        "description",
        "priority",
        "status",
        "due_date",
        "completed_at",
        "category",
        "recurrence",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"Unsupported task fields: {', '.join(sorted(unknown))}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            before = _fetch_task(cur, task_id=task_id, user_id=user_id)
            if before is None:
                return None
            assignments = [f"{field} = %s" for field in changes]
            values = list(changes.values())
            values.extend([task_id, user_id])
            cur.execute(
                f"""
                UPDATE tasks
                SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s;
                """,
                values,
            )
            after = _fetch_task(cur, task_id=task_id, user_id=user_id)
            assert after is not None
            _record_action(
                cur,
                user_id=user_id,
                task_id=task_id,
                action=action,
                before=before,
                after=after,
            )
            conn.commit()
            return after


def delete_task_record(*, task_id: str, user_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            before = _fetch_task(cur, task_id=task_id, user_id=user_id)
            if before is None:
                return None
            cur.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s", (task_id, user_id))
            _record_action(
                cur,
                user_id=user_id,
                task_id=task_id,
                action="delete",
                before=before,
                after=None,
            )
            conn.commit()
            return before


def undo_latest_task_action(*, user_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, task_id, action, before_state
                FROM task_action_history
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                FOR UPDATE;
                """,
                (user_id,),
            )
            history = cur.fetchone()
            if history is None:
                return None
            history = dict(history)
            task_id = str(history["task_id"])
            action = history["action"]
            before = history["before_state"]

            if action == "create":
                cur.execute("DELETE FROM tasks WHERE id = %s AND user_id = %s", (task_id, user_id))
                restored = None
            elif before:
                values = [before.get(field) for field in TASK_FIELDS]
                cur.execute(
                    """
                    INSERT INTO tasks
                        (id, user_id, project_id, title, description, priority, status,
                         due_date, completed_at, created_at, updated_at,
                         category, source, recurrence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        project_id = EXCLUDED.project_id,
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        priority = EXCLUDED.priority,
                        status = EXCLUDED.status,
                        due_date = EXCLUDED.due_date,
                        completed_at = EXCLUDED.completed_at,
                        created_at = EXCLUDED.created_at,
                        updated_at = CURRENT_TIMESTAMP,
                        category = EXCLUDED.category,
                        source = EXCLUDED.source,
                        recurrence = EXCLUDED.recurrence;
                    """,
                    values,
                )
                restored = _fetch_task(cur, task_id=task_id, user_id=user_id)
            else:
                restored = None

            cur.execute("DELETE FROM task_action_history WHERE id = %s", (history["id"],))
            conn.commit()
            return {"action": action, "task_id": task_id, "task": restored}
