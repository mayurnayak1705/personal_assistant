"""One-time local Gmail OAuth setup."""

from __future__ import annotations

import argparse

from mcp_servers.gmail.auth import authorize


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect the personal assistant to Gmail")
    parser.add_argument("client_secret", help="Path to the Google OAuth desktop client JSON")
    parser.add_argument("--token", help="Optional output token path")
    args = parser.parse_args()
    destination = authorize(args.client_secret, args.token)
    print(f"Gmail authorization saved to {destination}")


if __name__ == "__main__":
    main()
