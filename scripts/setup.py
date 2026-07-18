#!/usr/bin/env python3
"""Validate and initialize a local Deep Thought checkout."""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import psycopg
from psycopg import sql


load_dotenv(ROOT / ".env", override=True)

RUNTIME_IMPORTS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "langgraph": "langgraph",
    "langchain": "langchain",
    "langchain_openai": "langchain-openai",
    "langchain_anthropic": "langchain-anthropic",
    "openai": "openai",
    "anthropic": "anthropic",
    "mcp": "mcp",
    "fastmcp": "fastmcp",
    "psycopg": "psycopg[binary]",
    "chromadb": "chromadb",
    "googleapiclient": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "keyring": "keyring",
}


def status(symbol: str, message: str) -> None:
    print(f"{symbol} {message}", flush=True)


def database_config(database: str | None = None) -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": database or os.getenv("POSTGRES_DB", "ai_assistant_memory"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


def check_python() -> bool:
    valid = sys.version_info >= (3, 11)
    status("✓" if valid else "✗", f"Python {sys.version.split()[0]} ({'supported' if valid else '3.11+ required'})")
    return valid


def check_dependencies() -> bool:
    missing = [package for module, package in RUNTIME_IMPORTS.items() if importlib.util.find_spec(module) is None]
    if missing:
        status("✗", f"Missing Python packages: {', '.join(missing)}")
        status("→", "Run: python -m pip install -r requirements.txt")
        return False
    status("✓", "Python runtime dependencies are installed")
    return True


def check_environment() -> bool:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        status("✗", ".env is missing (copy .env.example to .env)")
        return False
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    openai_ready = bool(openai_key and not openai_key.startswith("replace_"))
    anthropic_ready = bool(anthropic_key and not anthropic_key.startswith("replace_"))
    if not openai_ready and not anthropic_ready:
        status("✗", "Configure OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
        return False
    providers = ", ".join(
        name for name, ready in (("OpenAI", openai_ready), ("Anthropic", anthropic_ready)) if ready
    )
    status("✓", f".env and model provider are configured ({providers})")
    return True


def check_go() -> bool:
    executable = shutil.which("go")
    if not executable:
        status("!", "Go is not installed; WhatsApp will remain unavailable")
        return False
    try:
        result = subprocess.run(
            [executable, "version"], capture_output=True, text=True, check=True, timeout=10
        )
        status("✓", result.stdout.strip())
        return True
    except (subprocess.SubprocessError, OSError) as exc:
        status("!", f"Could not run Go; WhatsApp will remain unavailable: {exc}")
        return False


def connect_target():
    return psycopg.connect(**database_config())


def create_database_if_needed(*, allow_create: bool) -> bool:
    target = os.getenv("POSTGRES_DB", "ai_assistant_memory")
    try:
        with connect_target() as connection:
            connection.execute("SELECT 1")
        status("✓", f"PostgreSQL database '{target}' is reachable")
        return True
    except psycopg.errors.InvalidCatalogName:
        if not allow_create:
            status("✗", f"PostgreSQL database '{target}' does not exist")
            return False
    except Exception as exc:
        status("✗", f"Could not connect to PostgreSQL database '{target}': {exc}")
        status("→", "Check that PostgreSQL is running and verify the POSTGRES_* values in .env")
        return False

    maintenance = os.getenv("POSTGRES_MAINTENANCE_DB", "postgres")
    try:
        config = database_config(maintenance)
        connection = psycopg.connect(**config, autocommit=True)
        try:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (target,)
            ).fetchone()
            if not exists:
                connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
                status("✓", f"Created PostgreSQL database '{target}'")
        finally:
            connection.close()
        return True
    except Exception as exc:
        status("✗", f"Could not create PostgreSQL database '{target}': {exc}")
        status("→", f"Create it with a privileged role, then rerun: createdb {target}")
        return False


def apply_postgres_schema() -> bool:
    schema_path = ROOT / "docs" / "postgres-schema.sql"
    try:
        with connect_target() as connection:
            connection.execute(schema_path.read_text(encoding="utf-8"))
            connection.commit()

        # These functions are idempotent and create the remaining application
        # tables/indexes used by startup and background integrations.
        from action_history_store import init_action_history_schema
        from daily_briefing_store import init_daily_briefing_schema
        from mcp_servers.gmail.storage import init_gmail_schema
        from mcp_servers.tasks.storage import init_task_schema
        from user_profile_store import init_user_profile_schema
        from working_context_store import init_working_context_schema

        for initializer in (
            init_task_schema,
            init_gmail_schema,
            init_working_context_schema,
            init_action_history_schema,
            init_daily_briefing_schema,
            init_user_profile_schema,
        ):
            initializer()
        status("✓", "PostgreSQL schema and application tables are ready")
        return True
    except Exception as exc:
        status("✗", f"Could not initialize PostgreSQL schema: {exc}")
        return False


def check_postgres_tables() -> bool:
    required = {"memories", "chat_history", "user_profiles", "user_facts", "reminders", "tasks"}
    try:
        with connect_target() as connection:
            rows = connection.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ).fetchall()
        present = {row[0] for row in rows}
        missing = sorted(required - present)
        if missing:
            status("✗", f"PostgreSQL is missing tables: {', '.join(missing)}")
            return False
        status("✓", "Required PostgreSQL tables are present")
        return True
    except Exception as exc:
        status("✗", f"PostgreSQL check failed: {exc}")
        return False


def prepare_local_storage() -> None:
    paths = [
        Path(os.getenv("CHROMA_PATH", ROOT / "Databases" / "Chroma")).expanduser(),
        Path(os.getenv("DEEP_THOUGHT_CREDENTIALS_DIR", Path.home() / ".deep-thought" / "credentials")).expanduser(),
        Path(os.getenv("EXPENSE_DB_PATH", ROOT / "mcp_servers" / "expense" / "server" / "expenses.db")).expanduser().parent,
        Path(os.getenv("WHATSMEOW_SESSION_DB", ROOT / "mcp_servers" / "whatsappmeow" / "whatsmeow-session.db")).expanduser().parent,
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    try:
        paths[1].chmod(0o700)
    except OSError:
        pass
    from expense_email_ingestion import init_schema as init_expense_import_schema
    from mcp_servers.expense.server.main import init_db as init_expense_schema

    init_expense_schema()
    init_expense_import_schema()
    status("✓", "Local storage directories and expense tables are ready")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and initialize Deep Thought")
    parser.add_argument("--check-only", action="store_true", help="validate without creating databases, tables or directories")
    parser.add_argument("--skip-database", action="store_true", help="skip all PostgreSQL checks and initialization")
    parser.add_argument("--no-create-database", action="store_true", help="do not attempt CREATE DATABASE when it is missing")
    args = parser.parse_args()

    print("\nDeep Thought setup\n------------------")
    required_ok = check_python() & check_dependencies() & check_environment()
    check_go()  # WhatsApp is optional, so this is advisory.

    database_ok = True
    if not args.skip_database:
        database_ok = create_database_if_needed(
            allow_create=not args.check_only and not args.no_create_database
        )
        if database_ok:
            database_ok = check_postgres_tables() if args.check_only else apply_postgres_schema()

    if not args.check_only:
        prepare_local_storage()

    if required_ok and database_ok:
        print("\nSetup complete. Start Deep Thought with:\n  uvicorn main:app --reload\n")
        return 0
    print("\nSetup needs attention. Fix the items marked ✗ and run this command again.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
