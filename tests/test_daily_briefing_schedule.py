from datetime import time

from Agent_Definations.planner import _format_briefing_time, _parse_briefing_time


def test_parse_briefing_time_from_short_follow_up():
    assert _parse_briefing_time("9 am") == time(9, 0)


def test_parse_briefing_time_from_full_request():
    assert _parse_briefing_time("Schedule my daily briefing at 09:30 AM") == time(9, 30)


def test_parse_24_hour_time():
    assert _parse_briefing_time("at 08:45") == time(8, 45)


def test_format_briefing_time():
    assert _format_briefing_time(time(9, 0)) == "9:00 AM"
