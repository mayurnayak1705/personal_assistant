// whatsmeow-mcp is a small MCP (Model Context Protocol) server that exposes
// three tools to an MCP-compatible host (e.g. Claude Desktop):
//
//   - list_contacts   find contacts by name
//   - read_messages   read recent messages with a contact, by name
//   - send_message    send a text message to a contact, by name
//
// It reuses an already-paired whatsmeow session (see the companion
// whatsmeow-demo project for the QR pairing step) and keeps its own local
// log of messages, since whatsmeow itself only streams live events rather
// than storing message history for you.
//
// IMPORTANT: stdout is reserved for JSON-RPC protocol messages. All logging
// goes to stderr. Never fmt.Println/log to stdout - it will corrupt the
// protocol stream and the host will fail to parse responses.
package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
	"sync"
	"time"

	_ "modernc.org/sqlite"

	"go.mau.fi/whatsmeow"
	waProto "go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
)

// ---------- config ----------

func sessionDBPath() string {
	if p := os.Getenv("WHATSMEOW_SESSION_DB"); p != "" {
		return p
	}
	return "whatsmeow-session.db"
}

func logDBPath() string {
	if p := os.Getenv("WHATSMEOW_LOG_DB"); p != "" {
		return p
	}
	return "whatsmeow-message-log.db"
}

// ---------- message log (our own history, since whatsmeow doesn't keep one) ----------

type messageRecord struct {
	ID        int64
	Timestamp time.Time
	ChatJID   string
	SenderJID string
	FromMe    bool
	Body      string
}

func openLogDB(path string) (*sql.DB, error) {
	// One connection + busy_timeout avoids SQLITE_BUSY under concurrent
	// writes, which is what caused the "database is locked" errors.
	dsn := fmt.Sprintf("file:%s?_pragma=busy_timeout(10000)&_pragma=journal_mode(WAL)", path)
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	_, err = db.Exec(`
		CREATE TABLE IF NOT EXISTS messages (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			timestamp INTEGER NOT NULL,
			chat_jid TEXT NOT NULL,
			sender_jid TEXT NOT NULL,
			from_me INTEGER NOT NULL,
			body TEXT NOT NULL
		)
	`)
	if err != nil {
		return nil, err
	}
	return db, nil
}

func logMessage(db *sql.DB, rec messageRecord) error {
	_, err := db.Exec(
		`INSERT INTO messages (timestamp, chat_jid, sender_jid, from_me, body) VALUES (?, ?, ?, ?, ?)`,
		rec.Timestamp.Unix(), rec.ChatJID, rec.SenderJID, rec.FromMe, rec.Body,
	)
	return err
}

func recentMessages(db *sql.DB, chatJID string, limit int) ([]messageRecord, error) {
	rows, err := db.Query(
		`SELECT timestamp, chat_jid, sender_jid, from_me, body FROM messages
		 WHERE chat_jid = ? ORDER BY timestamp DESC LIMIT ?`,
		chatJID, limit,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []messageRecord
	for rows.Next() {
		var rec messageRecord
		var ts int64
		var fromMe int
		if err := rows.Scan(&ts, &rec.ChatJID, &rec.SenderJID, &fromMe, &rec.Body); err != nil {
			return nil, err
		}
		rec.Timestamp = time.Unix(ts, 0)
		rec.FromMe = fromMe != 0
		out = append(out, rec)
	}
	// reverse to chronological order (oldest first)
	for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
		out[i], out[j] = out[j], out[i]
	}
	return out, rows.Err()
}

func incomingMessagesAfter(db *sql.DB, afterID *int64, limit int) ([]messageRecord, int64, error) {
	var latestID int64
	if err := db.QueryRow(`SELECT COALESCE(MAX(id), 0) FROM messages`).Scan(&latestID); err != nil {
		return nil, 0, err
	}

	// An omitted cursor initializes a UI subscriber at the current end of the
	// log. This prevents replaying the entire message history on every reload.
	if afterID == nil {
		return []messageRecord{}, latestID, nil
	}

	rows, err := db.Query(
		`SELECT id, timestamp, chat_jid, sender_jid, from_me, body FROM messages
		 WHERE id > ? AND from_me = 0 ORDER BY id ASC LIMIT ?`,
		*afterID, limit,
	)
	if err != nil {
		return nil, latestID, err
	}
	defer rows.Close()

	out := make([]messageRecord, 0)
	for rows.Next() {
		var rec messageRecord
		var ts int64
		var fromMe int
		if err := rows.Scan(&rec.ID, &ts, &rec.ChatJID, &rec.SenderJID, &fromMe, &rec.Body); err != nil {
			return nil, latestID, err
		}
		rec.Timestamp = time.Unix(ts, 0)
		rec.FromMe = fromMe != 0
		out = append(out, rec)
	}
	return out, latestID, rows.Err()
}

// ---------- contact resolution ----------

// contactMatch resolves a human-typed name to a JID by scanning whatsmeow's
// local contact store. It returns an error listing candidates if the name
// is ambiguous, or a "not found" error if nothing matches.
func contactMatch(ctx context.Context, client *whatsmeow.Client, query string) (types.JID, string, error) {
	contacts, err := client.Store.Contacts.GetAllContacts(ctx)
	if err != nil {
		return types.JID{}, "", fmt.Errorf("failed to load contacts: %w", err)
	}
	q := strings.ToLower(strings.TrimSpace(query))
	if q == "" {
		return types.JID{}, "", fmt.Errorf("empty contact name")
	}

	type candidate struct {
		jid   types.JID
		name  string
		phone string
	}
	var exact, partial []candidate
	phoneQuery := strings.TrimPrefix(q, "+")
	phoneQueryIsNumeric := phoneQuery != "" && strings.IndexFunc(phoneQuery, func(r rune) bool {
		return r < '0' || r > '9'
	}) == -1

	for jid, info := range contacts {
		phone := phoneNumberForJID(ctx, client, jid)
		if phoneQueryIsNumeric && phone == phoneQuery {
			name := preferredContactName(info.FullName, info.PushName, info.BusinessName, info.FirstName, jid.User)
			exact = append(exact, candidate{jid, name, phone})
			continue
		}
		names := []string{info.FullName, info.PushName, info.BusinessName, info.FirstName}
		for _, n := range names {
			if n == "" {
				continue
			}
			ln := strings.ToLower(n)
			if ln == q {
				exact = append(exact, candidate{jid, n, phone})
				break
			} else if strings.Contains(ln, q) {
				partial = append(partial, candidate{jid, n, phone})
				break
			}
		}
	}

	pick := exact
	if len(pick) == 0 {
		pick = partial
	}
	// WhatsApp may expose the same person through both a phone-number JID and
	// a privacy LID. They are aliases, not two recipients, so collapse them by
	// the resolved phone number before deciding that a name is ambiguous.
	byPhone := make(map[string]candidate)
	for _, item := range pick {
		existing, found := byPhone[item.phone]
		if !found || (existing.jid.Server != types.DefaultUserServer && item.jid.Server == types.DefaultUserServer) {
			byPhone[item.phone] = item
		}
	}
	pick = pick[:0]
	for _, item := range byPhone {
		pick = append(pick, item)
	}
	sort.Slice(pick, func(i, j int) bool {
		if pick[i].name == pick[j].name {
			return pick[i].phone < pick[j].phone
		}
		return pick[i].name < pick[j].name
	})

	switch len(pick) {
	case 0:
		return types.JID{}, "", fmt.Errorf("no contact found matching %q", query)
	case 1:
		return pick[0].jid, pick[0].name, nil
	default:
		var names []string
		for _, c := range pick {
			names = append(names, fmt.Sprintf("%s (%s)", c.name, c.jid.User))
		}
		return types.JID{}, "", fmt.Errorf("multiple contacts match %q: %s - be more specific", query, strings.Join(names, ", "))
	}
}

func phoneNumberForJID(ctx context.Context, client *whatsmeow.Client, jid types.JID) string {
	jid = jid.ToNonAD()
	if jid.Server == types.HiddenUserServer {
		pn, err := client.Store.LIDs.GetPNForLID(ctx, jid)
		if err == nil && !pn.IsEmpty() {
			return pn.User
		}
	}
	return jid.User
}

func preferredContactName(names ...string) string {
	for _, name := range names {
		if strings.TrimSpace(name) != "" {
			return name
		}
	}
	return "Unknown contact"
}

func contactNameForJID(ctx context.Context, client *whatsmeow.Client, rawJID string) string {
	jid, err := types.ParseJID(rawJID)
	if err != nil {
		return rawJID
	}
	contacts, err := client.Store.Contacts.GetAllContacts(ctx)
	if err != nil {
		return jid.User
	}
	info, ok := contacts[jid.ToNonAD()]
	if !ok {
		return jid.User
	}
	return preferredContactName(info.FullName, info.PushName, info.BusinessName, info.FirstName, jid.User)
}

func extractText(msg *waProto.Message) string {
	if msg == nil {
		return ""
	}
	if conv := msg.GetConversation(); conv != "" {
		return conv
	}
	if ext := msg.GetExtendedTextMessage(); ext != nil {
		return ext.GetText()
	}
	return ""
}

// ---------- MCP plumbing (JSON-RPC 2.0 over newline-delimited stdio) ----------

type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id,omitempty"`
	Result  interface{}     `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type toolDef struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	InputSchema map[string]interface{} `json:"inputSchema"`
}

type toolCallParams struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
}

var stdoutMu sync.Mutex

func writeResponse(resp rpcResponse) {
	resp.JSONRPC = "2.0"
	data, err := json.Marshal(resp)
	if err != nil {
		return
	}
	stdoutMu.Lock()
	defer stdoutMu.Unlock()
	os.Stdout.Write(data)
	os.Stdout.Write([]byte("\n"))
}

func toolResult(text string, isError bool) map[string]interface{} {
	return map[string]interface{}{
		"content": []map[string]interface{}{
			{"type": "text", "text": text},
		},
		"isError": isError,
	}
}

func jsonToolResult(value interface{}) map[string]interface{} {
	data, err := json.Marshal(value)
	if err != nil {
		return toolResult(fmt.Sprintf("failed to encode tool result: %v", err), true)
	}
	return toolResult(string(data), false)
}

func tools() []toolDef {
	return []toolDef{
		{
			Name:        "list_contacts",
			Description: "Find WhatsApp contacts by name (substring match). Use this first if you're not sure of the exact contact name.",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"query": map[string]interface{}{
						"type":        "string",
						"description": "Partial or full contact name to search for. Leave empty to list all known contacts.",
					},
				},
			},
		},
		{
			Name:        "read_messages",
			Description: "Read recent messages exchanged with a contact, identified by name. Only messages received/sent while this server was running are available - it does not fetch WhatsApp's own history.",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"contact": map[string]interface{}{
						"type":        "string",
						"description": "Contact name (or unambiguous partial name) to read messages with.",
					},
					"limit": map[string]interface{}{
						"type":        "integer",
						"description": "Max number of messages to return, most recent first internally but returned oldest-first. Default 20.",
					},
				},
				"required": []string{"contact"},
			},
		},
		{
			Name:        "send_message",
			Description: "Send a text message to a contact, identified by name.",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"contact": map[string]interface{}{
						"type":        "string",
						"description": "Contact name (or unambiguous partial name) to send the message to.",
					},
					"message": map[string]interface{}{
						"type":        "string",
						"description": "Text of the message to send.",
					},
				},
				"required": []string{"contact", "message"},
			},
		},
		{
			Name:        "poll_messages",
			Description: "Return new incoming WhatsApp text messages after a message-log cursor. Omit after_id once to initialize at the current cursor without replaying old messages.",
			InputSchema: map[string]interface{}{
				"type": "object",
				"properties": map[string]interface{}{
					"after_id": map[string]interface{}{
						"type":        "integer",
						"description": "Return incoming messages whose log ID is greater than this cursor.",
					},
					"limit": map[string]interface{}{
						"type":        "integer",
						"description": "Maximum number of messages to return. Default 50, maximum 200.",
					},
				},
			},
		},
		{
			Name:        "disconnect_whatsapp",
			Description: "Unlink this companion device from WhatsApp and delete its local authentication session. A new QR scan is required before WhatsApp can be used again.",
			InputSchema: map[string]interface{}{
				"type": "object",
			},
		},
	}
}

func main() {
	ctx := context.Background()
	// stdout is the MCP transport, so even error logs would corrupt JSON-RPC.
	// Application failures below are still written explicitly to stderr.
	logger := waLog.Noop

	dsn := fmt.Sprintf(
		"file:%s?_pragma=foreign_keys(1)&_pragma=busy_timeout(10000)&_pragma=journal_mode(WAL)",
		sessionDBPath(),
	)

	db, err := sqlstore.New(ctx, "sqlite", dsn, logger)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to open session store: %v\n", err)
		os.Exit(1)
	}

	deviceStore, err := db.GetFirstDevice(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to load device: %v\n", err)
		os.Exit(1)
	}

	client := whatsmeow.NewClient(deviceStore, logger)

	if client.Store.ID == nil {
		fmt.Fprintln(os.Stderr, "no paired session found - run the QR pairing step first (see README), "+
			"then point WHATSMEOW_SESSION_DB at that same whatsmeow-session.db file")
		os.Exit(1)
	}

	logDB, err := openLogDB(logDBPath())
	if err != nil {
		fmt.Fprintf(os.Stderr, "failed to open message log db: %v\n", err)
		os.Exit(1)
	}

	client.AddEventHandler(func(rawEvt interface{}) {
		evt, ok := rawEvt.(*events.Message)
		if !ok {
			return
		}
		text := extractText(evt.Message)
		if text == "" {
			return
		}
		err := logMessage(logDB, messageRecord{
			Timestamp: evt.Info.Timestamp,
			ChatJID:   evt.Info.Chat.String(),
			SenderJID: evt.Info.Sender.String(),
			FromMe:    evt.Info.IsFromMe,
			Body:      text,
		})
		if err != nil {
			fmt.Fprintf(os.Stderr, "failed to log message: %v\n", err)
		}
	})

	if err := client.Connect(); err != nil {
		fmt.Fprintf(os.Stderr, "failed to connect: %v\n", err)
		os.Exit(1)
	}
	defer client.Disconnect()

	handleToolCall := func(name string, args map[string]interface{}) map[string]interface{} {
		switch name {
		case "list_contacts":
			query, _ := args["query"].(string)
			contacts, err := client.Store.Contacts.GetAllContacts(ctx)
			if err != nil {
				return toolResult(fmt.Sprintf("failed to load contacts: %v", err), true)
			}
			type contactResult struct {
				Name        string   `json:"name"`
				PhoneNumber string   `json:"phone_number"`
				JID         string   `json:"jid"`
				Aliases     []string `json:"aliases,omitempty"`
			}
			byPhone := make(map[string]*contactResult)
			ql := strings.ToLower(query)
			for jid, info := range contacts {
				names := []string{info.FullName, info.PushName, info.BusinessName, info.FirstName}
				name := preferredContactName(info.FullName, info.PushName, info.BusinessName, info.FirstName, "Unknown contact")
				phoneNumber := phoneNumberForJID(ctx, client, jid)
				phoneQuery := strings.TrimPrefix(ql, "+")
				nameMatches := ql == ""
				for _, candidateName := range names {
					if strings.Contains(strings.ToLower(candidateName), ql) {
						nameMatches = true
						break
					}
				}
				if !nameMatches && phoneNumber != phoneQuery {
					continue
				}
				match, found := byPhone[phoneNumber]
				if !found {
					match = &contactResult{Name: name, PhoneNumber: phoneNumber, JID: jid.ToNonAD().String()}
					byPhone[phoneNumber] = match
				}
				for _, aliasName := range names {
					if aliasName != "" {
						seenAlias := false
						for _, alias := range match.Aliases {
							if alias == aliasName {
								seenAlias = true
								break
							}
						}
						if !seenAlias {
							match.Aliases = append(match.Aliases, aliasName)
						}
					}
				}
				if jid.Server == types.DefaultUserServer {
					match.JID = jid.ToNonAD().String()
				}
			}
			matches := make([]contactResult, 0, len(byPhone))
			for _, match := range byPhone {
				sort.Strings(match.Aliases)
				if len(match.Aliases) > 0 {
					match.Name = match.Aliases[0]
					for _, alias := range match.Aliases {
						if strings.EqualFold(alias, query) {
							match.Name = alias
							break
						}
					}
				}
				matches = append(matches, *match)
			}
			sort.Slice(matches, func(i, j int) bool {
				if matches[i].Name == matches[j].Name {
					return matches[i].PhoneNumber < matches[j].PhoneNumber
				}
				return matches[i].Name < matches[j].Name
			})
			return jsonToolResult(map[string]interface{}{
				"query":    query,
				"count":    len(matches),
				"contacts": matches,
			})

		case "read_messages":
			contactName, _ := args["contact"].(string)
			limit := 20
			if l, ok := args["limit"].(float64); ok && l > 0 {
				limit = int(l)
			}
			jid, matchedName, err := contactMatch(ctx, client, contactName)
			if err != nil {
				return toolResult(err.Error(), true)
			}
			msgs, err := recentMessages(logDB, jid.ToNonAD().String(), limit)
			if err != nil {
				return toolResult(fmt.Sprintf("failed to read message log: %v", err), true)
			}
			if len(msgs) == 0 {
				return toolResult(fmt.Sprintf("No logged messages with %s yet. Note: only messages seen while this server was running are available.", matchedName), false)
			}
			var lines []string
			for _, m := range msgs {
				who := matchedName
				if m.FromMe {
					who = "me"
				}
				lines = append(lines, fmt.Sprintf("[%s] %s: %s", m.Timestamp.Format("2006-01-02 15:04:05"), who, m.Body))
			}
			return toolResult(strings.Join(lines, "\n"), false)

		case "send_message":
			contactName, _ := args["contact"].(string)
			body, _ := args["message"].(string)
			if body == "" {
				return toolResult("message text is required", true)
			}
			jid, matchedName, err := contactMatch(ctx, client, contactName)
			if err != nil {
				return toolResult(err.Error(), true)
			}
			_, err = client.SendMessage(ctx, jid, &waProto.Message{Conversation: &body})
			if err != nil {
				return toolResult(fmt.Sprintf("failed to send message to %s: %v", matchedName, err), true)
			}
			_ = logMessage(logDB, messageRecord{
				Timestamp: time.Now(),
				ChatJID:   jid.ToNonAD().String(),
				SenderJID: client.Store.ID.String(),
				FromMe:    true,
				Body:      body,
			})
			return toolResult(fmt.Sprintf("Message sent to %s.", matchedName), false)

		case "poll_messages":
			limit := 50
			if l, ok := args["limit"].(float64); ok && l > 0 {
				limit = int(l)
			}
			if limit > 200 {
				limit = 200
			}
			var afterID *int64
			if raw, ok := args["after_id"].(float64); ok && raw >= 0 {
				cursor := int64(raw)
				afterID = &cursor
			}
			events, latestID, err := incomingMessagesAfter(logDB, afterID, limit)
			if err != nil {
				return toolResult(fmt.Sprintf("failed to poll message log: %v", err), true)
			}
			type messageEvent struct {
				ID          int64  `json:"id"`
				Timestamp   string `json:"timestamp"`
				ContactName string `json:"contact_name"`
				PhoneNumber string `json:"phone_number"`
				ChatJID     string `json:"chat_jid"`
				Body        string `json:"body"`
			}
			out := make([]messageEvent, 0, len(events))
			for _, event := range events {
				senderJID, parseErr := types.ParseJID(event.SenderJID)
				phoneNumber := event.SenderJID
				if parseErr == nil {
					phoneNumber = phoneNumberForJID(ctx, client, senderJID)
				}
				out = append(out, messageEvent{
					ID:          event.ID,
					Timestamp:   event.Timestamp.UTC().Format(time.RFC3339),
					ContactName: contactNameForJID(ctx, client, event.SenderJID),
					PhoneNumber: phoneNumber,
					ChatJID:     event.ChatJID,
					Body:        event.Body,
				})
			}
			cursor := latestID
			// If the limit was reached, continue from the last delivered event
			// next time instead of skipping a larger burst of inbound messages.
			if len(events) == limit && len(events) > 0 {
				cursor = events[len(events)-1].ID
			}
			return jsonToolResult(map[string]interface{}{
				"cursor":   cursor,
				"messages": out,
			})

		case "disconnect_whatsapp":
			if err := client.Logout(ctx); err != nil {
				return toolResult(fmt.Sprintf("failed to unlink WhatsApp: %v", err), true)
			}
			return toolResult("WhatsApp device unlinked and local session removed.", false)

		default:
			return toolResult(fmt.Sprintf("unknown tool: %s", name), true)
		}
	}

	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 1024*1024), 10*1024*1024)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var req rpcRequest
		if err := json.Unmarshal(line, &req); err != nil {
			continue
		}

		switch req.Method {
		case "initialize":
			writeResponse(rpcResponse{ID: req.ID, Result: map[string]interface{}{
				"protocolVersion": "2024-11-05",
				"capabilities": map[string]interface{}{
					"tools": map[string]interface{}{},
				},
				"serverInfo": map[string]interface{}{
					"name":    "whatsapp-mcp",
					"version": "0.1.0",
				},
			}})

		case "notifications/initialized":
			// no response required for notifications

		case "tools/list":
			writeResponse(rpcResponse{ID: req.ID, Result: map[string]interface{}{
				"tools": tools(),
			}})

		case "tools/call":
			var params toolCallParams
			if err := json.Unmarshal(req.Params, &params); err != nil {
				writeResponse(rpcResponse{ID: req.ID, Error: &rpcError{Code: -32602, Message: "invalid params"}})
				continue
			}
			result := handleToolCall(params.Name, params.Arguments)
			writeResponse(rpcResponse{ID: req.ID, Result: result})

		default:
			if len(req.ID) > 0 {
				writeResponse(rpcResponse{ID: req.ID, Error: &rpcError{Code: -32601, Message: "method not found"}})
			}
		}
	}
}
