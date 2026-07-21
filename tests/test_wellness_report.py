from datetime import date

from app.features.wellness import store as wellness_store


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        return None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return FakeCursor(self.rows)


def test_report_ignores_blank_optional_numbers_and_accepts_measurements(monkeypatch):
    today = date.today()
    rows = [
        {
            "log_date": today,
            "kind": "journal",
            "data": {"sleep_hours": "", "mood": "not supplied"},
        },
        {
            "log_date": today,
            "kind": "workout",
            "data": {"active_minutes": "45", "steps": "6000"},
        },
        {
            "log_date": today,
            "kind": "measurement",
            "data": {"weight_kg": "79.5"},
        },
    ]
    profile = {
        "current_weight_kg": 80,
        "baseline_weight_kg": 80,
        "target_value": 75,
        "height_cm": 175,
        "age": 30,
        "biological_sex": "prefer not to say",
    }
    monkeypatch.setattr(wellness_store, "get_profile", lambda _user_id: profile)
    monkeypatch.setattr(wellness_store, "get_connection", lambda: FakeConnection(rows))

    result = wellness_store.report("local-user", 30)

    assert result["summary"]["active_minutes"] == 45
    assert result["summary"]["steps"] == 6000
    assert result["summary"]["this_week"]["sleep_hours"] is None
    assert result["daily"][0]["measurement"] == 1
    assert result["daily"][0]["weight_kg"] == 79.5
