from __future__ import annotations

import unittest
from unittest.mock import Mock

from mcp_servers.calendar.events import create_meeting, normalize_attendees


class CalendarMeetingTests(unittest.TestCase):
    def test_create_meeting_builds_google_meet_and_invites(self) -> None:
        created = {
            "id": "event-123",
            "summary": "Startup discussion",
            "start": {"dateTime": "2026-07-17T22:00:00+05:30"},
            "end": {"dateTime": "2026-07-17T22:30:00+05:30"},
            "attendees": [{"email": "xyz@gmail.com"}],
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
            "htmlLink": "https://calendar.google.com/event?eid=123",
            "status": "confirmed",
        }
        request = Mock()
        request.execute.return_value = created
        events = Mock()
        events.insert.return_value = request
        service = Mock()
        service.events.return_value = events

        result = create_meeting(
            service,
            calendar_id="primary",
            title="Startup discussion",
            start_time="2026-07-17T22:00:00+05:30",
            attendee_emails=["XYZ@gmail.com", "xyz@gmail.com"],
            duration_minutes=30,
            description="Discuss the startup",
            timezone_name="Asia/Kolkata",
        )

        self.assertEqual(result["meet_url"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual(result["attendees"], ["xyz@gmail.com"])
        kwargs = events.insert.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "primary")
        self.assertEqual(kwargs["conferenceDataVersion"], 1)
        self.assertEqual(kwargs["sendUpdates"], "all")
        self.assertEqual(
            kwargs["body"]["conferenceData"]["createRequest"]["conferenceSolutionKey"]["type"],
            "hangoutsMeet",
        )
        self.assertEqual(kwargs["body"]["attendees"], [{"email": "xyz@gmail.com"}])

    def test_rejects_invalid_email(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid attendee email"):
            normalize_attendees(["not-an-email"])

    def test_requires_at_least_one_attendee(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one attendee"):
            normalize_attendees([])


if __name__ == "__main__":
    unittest.main()
