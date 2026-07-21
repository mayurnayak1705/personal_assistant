# Contributing

Thanks for helping improve Deep Thought.

## Before starting

1. Search existing issues and pull requests.
2. For a large feature or schema change, open an issue describing the user
   flow, security implications and proposed MCP boundary.
3. Keep each change focused. Do not include tokens, OAuth JSON, WhatsApp
   sessions, databases or personal messages in commits or fixtures.

## Development setup

Follow the root README, copy `.env.example` to `.env`, initialize PostgreSQL
with `docs/postgres-schema.sql`, then run:

```bash
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/setup.py
uvicorn main:app --reload
```

## Design expectations

- Route action-oriented requests through the planner.
- Keep integration execution inside MCP clients/servers.
- Return structured tool results and never claim success without evidence.
- Require clarification for ambiguous destructive actions or contacts.
- Store timestamps with an explicit timezone at system boundaries.
- Make database migrations idempotent and preserve existing user data.
- Avoid hard-coded users, credentials, contacts, categories and machine paths.
- Redact sensitive values from logs and error messages.

## Verification

At minimum, run checks relevant to the edited components:

```bash
python -m compileall -q main.py app mcp_servers
python -m pytest -q
node --check static/js/app.js
git diff --check
```

Go changes should also run from `mcp_servers/whatsappmeow`:

```bash
gofmt -w <changed-go-files>
go test ./...
```

If a test requires a real external account, state that clearly in the pull
request and test with non-production data.

## Pull requests

Include:

- What changed and why
- User-visible behavior
- Data/schema implications
- Security/privacy implications
- Commands run and their results
- Screenshots for meaningful UI changes
