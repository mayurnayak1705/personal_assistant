# Google Calendar MCP integration

The Calendar MCP creates Google Calendar events, invites one or more email
addresses, emails invitations, and generates a unique Google Meet link for each
event. It can also list upcoming events and cancel an event while notifying its
attendees.

## Google Cloud and OAuth setup

1. In a Google Cloud project, enable the **Google Calendar API**.
2. Also enable the **Gmail API** because Deep Thought uses one shared Google
   authorization for both integrations.
3. Configure the OAuth consent screen and add your Google account as a test
   user while the app is in testing mode.
4. Create an OAuth client with application type **Desktop app** and download its
   JSON file.
5. Start Deep Thought, open **Settings**, then select **Add OAuth JSON** beside
   Gmail or Google Calendar.
6. Select the downloaded Desktop OAuth JSON and choose **Connect**.
7. Complete Google sign-in and approve the Gmail and Calendar permissions.

The browser consent flow requests `gmail.modify` and `calendar.events`. Gmail
and Calendar intentionally share this one authorization, so connecting either
card enables both integrations. The OAuth JSON is validated before saving.
Refresh tokens are stored in the operating-system keyring when available, with
a mode-`0600` local-file fallback under `~/.deep-thought/credentials` (or
`DEEP_THOUGHT_CREDENTIALS_DIR`). They are never stored in the repository.

For the full open-source setup flow, see [Google OAuth](google-oauth.md).

Optional environment variables:

```dotenv
APP_TIMEZONE=Asia/Kolkata
GOOGLE_CALENDAR_ID=primary
```

Restart the FastAPI application after authorization. Verify the connection at
`GET /api/calendar/status`.

## Chat examples

```text
Schedule a call tomorrow at 10 PM with attendee@example.com regarding our startup discussion.

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
