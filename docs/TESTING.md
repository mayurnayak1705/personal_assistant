# Testing and release checks

Deep Thought uses three safety layers: pure unit tests, PostgreSQL integration
tests against a disposable database, and a manual integration checklist. The
automated suite **never** connects to a real Gmail, Calendar, WhatsApp account,
or model-provider account.

## Run locally

```bash
./.venv/bin/python -m pip install -r requirements-dev.txt
./.venv/bin/python -m pytest
```

To run only fast tests while developing:

```bash
./.venv/bin/python -m pytest -m "not integration"
```

The PostgreSQL test needs a separate disposable database. Do not point it at
your normal assistant database:

```bash
export POSTGRES_DB=deep_thought_test
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_test_database_password
./.venv/bin/python -m pytest -m integration
```

## Automated coverage

| Area | What must be covered |
| --- | --- |
| Routing and memory | Intent selection, references such as `send it`, and duplicate-action prevention |
| Tasks and reminders | Lifecycle updates, overdue/due notifications and acknowledgement |
| Gmail and Calendar | Mocked drafts/sends/events, invalid input and duplicate-event protection |
| WhatsApp | Exact vs ambiguous contacts, integration toggle and safe send behavior |
| Expenses | INR reports, filters, undo, bounded reports and transaction-email parsing |
| API/UI | Request validation, modal/panel behaviour, notification flows and responsive smoke tests |
| Database | Schema initialization and basic read/write against a temporary database |

## CI and releases

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`. It
performs syntax, critical lint, test, coverage, whitespace and secret checks using an
ephemeral PostgreSQL service.

`.github/workflows/release.yml` runs when a version tag such as `v1.0.1` is
pushed. It reruns the release suite, creates a source archive with SHA-256
checksum, and publishes a GitHub Release only if verification succeeds.

Create a release with:

```bash
git tag v1.0.1
git push origin v1.0.1
```

## Manual release checklist

Run these after the automated release passes, using a dedicated non-personal
test account where possible:

1. Start from a clean `.env` and run `python scripts/setup.py`.
2. Confirm first-run name/profile setup and dark/light themes.
3. Reconnect Gmail and Calendar OAuth; read one message and create one test
   event, then delete it.
4. Link WhatsApp using QR, receive a test message, send a test reply, then
   disconnect it.
5. Create a reminder and a task; check notification, sound and acknowledgement.
6. Verify a repeated `send it` does not create an additional external action.
7. Confirm `git status --ignored` contains no credentials, OAuth files,
   WhatsApp sessions, databases or user data intended for release.
