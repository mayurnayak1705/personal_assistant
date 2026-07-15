// whatsmeow-demo is a minimal CLI that shows how to:
//   1. Authenticate a WhatsApp session by scanning a QR code (session is
//      persisted to a local SQLite file so you only need to scan once).
//   2. Receive incoming text messages and print them to the terminal.
//   3. Send text messages to a phone number from the terminal.
//
// This is intentionally small and single-file so it's easy to read end to
// end. It's meant as a starting point, not a production bot framework.
package main

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/mdp/qrterminal/v3"
	_ "modernc.org/sqlite" // pure-Go sqlite driver, registers itself as "sqlite"

	"go.mau.fi/whatsmeow"
	waProto "go.mau.fi/whatsmeow/proto/waE2E"
	"go.mau.fi/whatsmeow/store/sqlstore"
	"go.mau.fi/whatsmeow/types"
	"go.mau.fi/whatsmeow/types/events"
	waLog "go.mau.fi/whatsmeow/util/log"
)

func main() {
	ctx := context.Background()
	logger := waLog.Stdout("Client", "INFO", true)

	// Session data (keys, registration info, etc.) lives in this file.
	// Delete it if you ever want to force a fresh QR login.
	container, err := sqlstore.New(ctx, "sqlite", "file:whatsmeow-session.db?_pragma=foreign_keys(1)", logger)
	if err != nil {
		panic(fmt.Errorf("failed to open session store: %w", err))
	}

	// GetFirstDevice returns the previously paired device, or a blank one
	// if this is the first run.
	deviceStore, err := container.GetFirstDevice(ctx)
	if err != nil {
		panic(fmt.Errorf("failed to load device: %w", err))
	}

	client := whatsmeow.NewClient(deviceStore, waLog.Stdout("Client", "INFO", true))
	client.AddEventHandler(makeEventHandler(client))

	if client.Store.ID == nil {
		// No session yet: request a QR code and print it to the terminal.
		if err := authenticateWithQR(ctx, client); err != nil {
			panic(err)
		}
	} else {
		// Already paired: just connect.
		if err := client.Connect(); err != nil {
			panic(fmt.Errorf("failed to connect: %w", err))
		}
	}
	defer client.Disconnect()

	fmt.Println("Connected. Type `send <phone_number> <message>` to send a text message.")
	fmt.Println("Phone numbers should include the country code, e.g. 15551234567 (no +, no leading 0).")
	fmt.Println("Type `quit` to exit.")

	go readCommands(ctx, client)

	// Block until Ctrl+C / SIGTERM.
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan
}

// authenticateWithQR requests a QR code from WhatsApp and renders it in the
// terminal. Scan it with WhatsApp on your phone: Settings > Linked Devices >
// Link a Device.
func authenticateWithQR(ctx context.Context, client *whatsmeow.Client) error {
	qrChan, err := client.GetQRChannel(ctx)
	if err != nil {
		return fmt.Errorf("failed to get QR channel: %w", err)
	}
	if err := client.Connect(); err != nil {
		return fmt.Errorf("failed to connect: %w", err)
	}
	for evt := range qrChan {
		switch evt.Event {
		case "code":
			fmt.Println("Scan this QR code with WhatsApp (Linked Devices > Link a Device):")
			qrterminal.GenerateHalfBlock(evt.Code, qrterminal.L, os.Stdout)
		case "success":
			fmt.Println("Pairing successful!")
		case "timeout":
			return fmt.Errorf("QR code timed out, restart the program to try again")
		default:
			if evt.Error != nil {
				fmt.Printf("Pairing event %q: %v\n", evt.Event, evt.Error)
			}
		}
	}
	return nil
}

// makeEventHandler returns a handler that prints incoming text messages.
// whatsmeow dispatches every event type through this single callback, so we
// switch on the concrete type we care about (events.Message) and ignore the
// rest (receipts, presence updates, connection state, etc.).
func makeEventHandler(client *whatsmeow.Client) func(evt interface{}) {
	return func(rawEvt interface{}) {
		switch evt := rawEvt.(type) {
		case *events.Message:
			text := extractText(evt.Message)
			if text == "" {
				return // media, reactions, etc. - skipped for this small demo
			}
			sender := evt.Info.Sender.User
			chat := evt.Info.Chat.String()
			fmt.Printf("[%s] from %s (chat %s): %s\n", evt.Info.Timestamp.Format("15:04:05"), sender, chat, text)
		case *events.Connected:
			fmt.Println("(connected to WhatsApp servers)")
		case *events.Disconnected:
			fmt.Println("(disconnected from WhatsApp servers)")
		case *events.LoggedOut:
			fmt.Println("(logged out - delete whatsmeow-session.db and restart to re-pair)")
		}
	}
}

// extractText pulls the plain-text body out of the handful of message types
// that carry one. Real chats will send other types too (images, stickers,
// replies, etc.) - extend this switch as needed.
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

// readCommands reads lines from stdin and handles `send <number> <text>`
// and `quit`.
func readCommands(ctx context.Context, client *whatsmeow.Client) {
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		if line == "quit" {
			os.Exit(0)
		}
		parts := strings.SplitN(line, " ", 3)
		if len(parts) < 3 || parts[0] != "send" {
			fmt.Println("Usage: send <phone_number> <message>")
			continue
		}
		number, body := parts[1], parts[2]
		if err := sendText(ctx, client, number, body); err != nil {
			fmt.Printf("Failed to send: %v\n", err)
		} else {
			fmt.Println("Sent.")
		}
	}
}

// sendText sends a plain-text message to the given phone number.
// number must include the country code, digits only (e.g. "15551234567").
func sendText(ctx context.Context, client *whatsmeow.Client, number, body string) error {
	jid := types.NewJID(number, types.DefaultUserServer)
	msg := &waProto.Message{
		Conversation: &body,
	}
	_, err := client.SendMessage(ctx, jid, msg)
	return err
}
