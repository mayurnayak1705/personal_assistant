# Daily briefing

The first app open at or after the user's configured morning time for each user
and local calendar date requests `GET /api/briefing/daily`. The default is 9:00
AM Asia/Kolkata. The browser checks once a minute while open, so a briefing also
appears when its scheduled time arrives without a refresh. PostgreSQL enforces
one persisted briefing per
`(user_id, briefing_date)`, so opening another tab or refreshing does not show
the card again. `force=true` regenerates it, and chat requests such as “give me
my daily briefing” route to the same aggregator with force enabled at any time.

Chat requests such as “schedule my daily briefing at 9 am” persist the user's
time in `daily_briefing_preferences`. Scheduling only confirms the saved time;
it does not generate or display a briefing immediately.

The welcome greeting is separate. The frontend reads `GET /api/user/profile`,
which derives morning/afternoon/evening from server time in `Asia/Kolkata` and
loads the user's name from the `user_facts` table. No display name is hardcoded
in the page or JavaScript.

The briefing aggregates independently:

- open tasks due today and open tasks overdue before today;
- already-due reminders and pending reminders later today;
- personal inbound WhatsApp messages since the previous briefing, or the last
  24 hours on first use (newsletter traffic and message bodies are excluded);
- the most-utilised currently active expense budget, when one exists.

Failures are isolated per integration and recorded in the structured
`availability` field. A disabled WhatsApp integration or unavailable expense
database therefore does not prevent task and reminder briefing content.
