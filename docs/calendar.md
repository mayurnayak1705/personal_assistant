# Google Calendar MCP integration

The Calendar MCP creates Google Calendar events, invites one or more email
addresses, emails invitations, and generates a unique Google Meet link for each
event. It can also list upcoming events and cancel an event while notifying its
attendees.

## Google Cloud and OAuth setup

1. In a Google Cloud project, enable the **Google Calendar API**.
2. Configure the OAuth consent screen and add your Google account as a test user
   while the app is in testing mode.
3. Create an OAuth client with application type **Desktop app** and download its
   JSON file.
4. From the repository root, run:

```bash
.venv/bin/python -m mcp_servers.calendar.setup_oauth /path/to/client_secret.json
```

The browser consent flow requests the narrow `calendar.events` scope. The saved
refresh token is written to `mcp_servers/calendar/token.json`, mode `0600`, and
is ignored by Git. Calendar and Gmail intentionally use separate token files.

Optional environment variables:

```dotenv
APP_TIMEZONE=Asia/Kolkata
GOOGLE_CALENDAR_ID=primary
CALENDAR_TOKEN_FILE=/custom/path/calendar-token.json
```

Restart the FastAPI application after authorization. Verify the connection at
`GET /api/calendar/status`.

## Chat examples

```text
Schedule a call tomorrow at 10 PM with xyz@gmail.com regarding our startup discussion.

Schedule a 45-minute product review on Friday at 3 PM with a@example.com and b@example.com.

Show my upcoming meetings.
```

If a date is omitted (for example, only “at 10 PM”), the planner asks for the
date instead of guessing. If duration is omitted, it defaults to 30 minutes.

The underlying MCP creation tool is `create_calendar_meeting`. Its important
arguments are `title`, ISO-8601 `start_time`, `attendee_emails`, optional
`duration_minutes`, `description`, and IANA `timezone`.

Google generates conference details asynchronously. The tool briefly refreshes
a newly created event when needed; in the uncommon case that generation is
still pending, it returns `created_meet_pending` and the Calendar event URL
instead of inventing a Meet link.
