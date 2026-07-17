# Gmail MCP integration

The Gmail MCP supports inbox search/read, unread mail, drafts, immediate sends,
threaded replies, mark-read, archive, and durable scheduled delivery. By
default Gmail uses the authenticated account as the From identity. An optional
`GMAIL_FROM_EMAIL` value must belong to that account or be a verified send-as
alias.

## OAuth

Gmail and Calendar use the shared Settings-based OAuth flow documented in
[`google-oauth.md`](google-oauth.md). Users provide their own Google Desktop
OAuth JSON. Tokens are stored in the OS keyring when available, with a
permission-restricted local fallback.

## Scheduled delivery

`schedule_email` writes the complete outgoing message and timezone-aware due
time to PostgreSQL. The Gmail client's background dispatcher checks every 15
seconds, atomically claims due records, and records `sent` or `failed` status.
If the backend is restarted after a due time, overdue scheduled messages are
sent when the Gmail service starts again. No local process can send while the
computer and backend are both off.

Internal dispatch is excluded from the planner's tool list. Direct send and
reply tools are available only under the Gmail planner's explicit-send rules.
