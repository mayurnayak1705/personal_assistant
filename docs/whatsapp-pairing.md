# WhatsApp pairing

Deep Thought links WhatsApp locally through the existing whatsmeow MCP server.
Users do not need to enter a phone number or copy credentials into a file.

## User flow

1. Start Deep Thought and open **Settings**.
2. Select **Connect** on the WhatsApp card.
3. On the phone, open WhatsApp and go to **Settings > Linked devices > Link a device**.
4. Scan the QR code shown by Deep Thought.
5. After WhatsApp confirms the link, the MCP messaging service starts automatically.

The linked-device session is stored in
`mcp_servers/whatsappmeow/whatsmeow-session.db`. It remains available after the
application is closed, so the QR code is only required for first-time setup or
after the linked device is removed from WhatsApp.

The WhatsApp switch controls sending and receiving without deleting the linked
session. Turning it back on reconnects the same account.

## Runtime requirements

- Go must be installed and available as `go`.
- The computer must be able to reach WhatsApp while pairing and while messages
  are being sent or received.
- Run the FastAPI application from the repository environment as usual. The API
  starts `pairing.go` for QR authentication and `mcp_server.go` for messaging.

## Optional custom session location

Set `WHATSMEOW_SESSION_DB` before starting the application to store the paired
session somewhere else. The pairing helper and MCP server must use the same
path.
