import asyncio
import unittest

from mcp_servers.calendar.client import CalendarMCPClient
from session_store import add_tool_events, get_tool_events, pop_session
from working_context import replay_protection_message


def event(integration, tool_name, arguments=None):
    return {
        "integration": integration,
        "tool_name": tool_name,
        "arguments": arguments or {},
        "success": True,
    }


class ShortTermActionMemoryTests(unittest.TestCase):
    def test_confirmation_does_not_replay_completed_send_or_meeting(self):
        self.assertIn(
            "already scheduled",
            replay_protection_message(
                "calendar_management", "send it", [event("calendar", "create_calendar_meeting")]
            ),
        )
        self.assertIn(
            "already sent",
            replay_protection_message(
                "whatsapp_messaging", "go ahead", [event("whatsapp", "send_message")]
            ),
        )
        self.assertIn(
            "already sent",
            replay_protection_message(
                "email_management", "yes", [event("gmail", "reply_to_email")]
            ),
        )

    def test_draft_can_still_be_sent(self):
        self.assertIsNone(
            replay_protection_message("email_management", "send it", [event("gmail", "draft_email")])
        )

    def test_calendar_duplicate_match_requires_same_meeting(self):
        args = {
            "title": "Product discussion",
            "start_time": "2026-07-19T14:00:00+05:30",
            "attendees": ["a@example.com", "b@example.com"],
        }
        previous = [event("calendar", "create_calendar_meeting", dict(args))]
        self.assertTrue(CalendarMCPClient._already_created(args, previous))
        changed = dict(args, start_time="2026-07-19T15:00:00+05:30")
        self.assertFalse(CalendarMCPClient._already_created(changed, previous))

    def test_session_events_are_available_without_database(self):
        async def run():
            conversation_id = "short-memory-test"
            await pop_session(conversation_id)
            await add_tool_events(conversation_id, [event("gmail", "send_email")])
            events = await get_tool_events(conversation_id)
            await pop_session(conversation_id)
            return events

        self.assertEqual(asyncio.run(run())[0]["tool_name"], "send_email")

