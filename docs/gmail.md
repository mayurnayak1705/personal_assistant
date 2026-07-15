# Gmail MCP integration

The Gmail MCP supports inbox search/read, unread mail, drafts, immediate sends,
threaded replies, mark-read, archive, and durable scheduled delivery. The
configured From identity is `mayurnayak1705@gmail.com`; Gmail will only accept
that address when it is the authenticated account or a verified send-as alias.

## OAuth

The integration uses Google's installed-app OAuth flow and the single
`gmail.modify` scope. The generated `mcp_servers/gmail/token.json` contains the
refresh token, is mode `0600`, and is ignored by Git.

To reconnect:

```bash
.venv/bin/python -m mcp_servers.gmail.setup_oauth /path/to/client_secret.json
```

## Scheduled delivery

`schedule_email` writes the complete outgoing message and timezone-aware due
time to PostgreSQL. The Gmail client's background dispatcher checks every 15
seconds, atomically claims due records, and records `sent` or `failed` status.
If the backend is restarted after a due time, overdue scheduled messages are
sent when the Gmail service starts again. No local process can send while the
computer and backend are both off.

Internal dispatch is excluded from the planner's tool list. Direct send and
reply tools are available only under the Gmail planner's explicit-send rules.
