// pairing provides a UI-friendly first-time WhatsApp authentication flow.
// It emits newline-delimited JSON only; the Python API turns those events into
// the Settings pairing modal and starts the MCP server after success.
package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image/png"
	"os"

	_ "modernc.org/sqlite"
	"rsc.io/qr"

	"go.mau.fi/whatsmeow"
	"go.mau.fi/whatsmeow/store/sqlstore"
	waLog "go.mau.fi/whatsmeow/util/log"
)

type pairingEvent struct {
	Status  string `json:"status"`
	QRImage string `json:"qr_image,omitempty"`
	Message string `json:"message,omitempty"`
}

func emitPairingEvent(event pairingEvent) {
	_ = json.NewEncoder(os.Stdout).Encode(event)
}

func pairingSessionDBPath() string {
	if path := os.Getenv("WHATSMEOW_SESSION_DB"); path != "" {
		return path
	}
	return "whatsmeow-session.db"
}

func qrDataURL(value string) (string, error) {
	code, err := qr.Encode(value, qr.M)
	if err != nil {
		return "", err
	}
	code.Scale = 7
	var output bytes.Buffer
	if err := png.Encode(&output, code.Image()); err != nil {
		return "", err
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(output.Bytes()), nil
}

func main() {
	ctx := context.Background()
	dsn := fmt.Sprintf(
		"file:%s?_pragma=foreign_keys(1)&_pragma=busy_timeout(10000)&_pragma=journal_mode(WAL)",
		pairingSessionDBPath(),
	)
	store, err := sqlstore.New(ctx, "sqlite", dsn, waLog.Noop)
	if err != nil {
		emitPairingEvent(pairingEvent{Status: "error", Message: fmt.Sprintf("failed to open session store: %v", err)})
		return
	}
	device, err := store.GetFirstDevice(ctx)
	if err != nil {
		emitPairingEvent(pairingEvent{Status: "error", Message: fmt.Sprintf("failed to load device: %v", err)})
		return
	}
	client := whatsmeow.NewClient(device, waLog.Noop)
	if client.Store.ID != nil {
		emitPairingEvent(pairingEvent{Status: "success", Message: "WhatsApp is already linked."})
		return
	}

	qrChannel, err := client.GetQRChannel(ctx)
	if err != nil {
		emitPairingEvent(pairingEvent{Status: "error", Message: fmt.Sprintf("failed to start QR pairing: %v", err)})
		return
	}
	if err := client.Connect(); err != nil {
		emitPairingEvent(pairingEvent{Status: "error", Message: fmt.Sprintf("failed to connect to WhatsApp: %v", err)})
		return
	}
	defer client.Disconnect()

	for event := range qrChannel {
		switch event.Event {
		case "code":
			image, encodeErr := qrDataURL(event.Code)
			if encodeErr != nil {
				emitPairingEvent(pairingEvent{Status: "error", Message: fmt.Sprintf("failed to render QR code: %v", encodeErr)})
				return
			}
			emitPairingEvent(pairingEvent{Status: "qr", QRImage: image, Message: "Scan this QR code with WhatsApp."})
		case "success":
			emitPairingEvent(pairingEvent{Status: "success", Message: "WhatsApp linked successfully."})
			return
		case "timeout":
			emitPairingEvent(pairingEvent{Status: "expired", Message: "The QR code expired. Start pairing again."})
			return
		default:
			if event.Error != nil {
				emitPairingEvent(pairingEvent{Status: "error", Message: event.Error.Error()})
				return
			}
		}
	}
}
