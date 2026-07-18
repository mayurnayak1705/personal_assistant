"""Database-backed local user identity and profile setup."""

from __future__ import annotations

import os

from Server.postgre_insert import get_connection


DEFAULT_USER_ID = os.getenv("DEEP_THOUGHT_USER_ID", "local-user")


def init_user_profile_schema() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id VARCHAR PRIMARY KEY,
                    display_name VARCHAR(120) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        connection.commit()


def get_user_profile(user_id: str) -> dict | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, display_name, created_at, updated_at
                FROM user_profiles
                WHERE user_id = %s;
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    if not row:
        return None
    display_name = str(row["display_name"]).strip()
    return {
        **row,
        "display_name": display_name,
        "first_name": display_name.split()[0],
    }


def save_user_profile(user_id: str, display_name: str) -> dict:
    cleaned_name = " ".join(str(display_name or "").split()).strip()
    if not cleaned_name:
        raise ValueError("Please enter your name.")
    if len(cleaned_name) > 120:
        raise ValueError("Name must be 120 characters or fewer.")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_profiles (user_id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET display_name = EXCLUDED.display_name,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING user_id, display_name, created_at, updated_at;
                """,
                (user_id, cleaned_name),
            )
            row = cursor.fetchone()
        connection.commit()

    return {
        **row,
        "first_name": cleaned_name.split()[0],
    }
