# Security policy

## Supported versions

This project is under active development. Security fixes are applied to the
latest default branch only.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials or personal
data. Contact the repository maintainer privately using the security-reporting
method configured on the hosting repository. Include affected versions,
reproduction steps, impact and any suggested mitigation.

The maintainer should add a private reporting email or enable GitHub private
vulnerability reporting before public release.

## Deployment warning

Deep Thought currently targets trusted local use. It has integrations capable
of reading email, sending messages, creating calendar events and accessing
personal data. Do not expose the FastAPI development server directly to the
public internet.

For any remote deployment, add authentication, authorization, CSRF protection,
TLS, rate limiting, secret management, audit retention controls and strict
network/database isolation.

## Sensitive local data

Never commit or share:

- `.env` files and API keys
- Google OAuth client JSON and access/refresh tokens
- WhatsApp session or message-log databases
- Expense SQLite databases
- PostgreSQL dumps containing personal information
- Chroma stores generated from private conversations
- Debug logs produced from real accounts

Revoke affected credentials and unlink WhatsApp immediately if any of these are
exposed.
