"""Safe PostgreSQL smoke tests for CI's disposable database."""

from __future__ import annotations

import uuid

import pytest

from app.features.profile.store import get_user_profile, init_user_profile_schema, save_user_profile
from app.features.wellness.store import add_log, report, save_profile


@pytest.mark.integration
def test_user_profile_schema_round_trip():
    """Prove the configured Postgres database accepts a real application write."""
    user_id = f"ci-{uuid.uuid4()}"
    init_user_profile_schema()
    saved = save_user_profile(user_id, "CI Test User")
    loaded = get_user_profile(user_id)

    assert saved["user_id"] == user_id
    assert loaded is not None
    assert loaded["display_name"] == "CI Test User"
    assert loaded["first_name"] == "CI"

@pytest.mark.integration
def test_wellness_profile_logs_and_report():
    user_id=f"wellness-{uuid.uuid4()}"
    save_profile(user_id,{"age":30,"biological_sex":"prefer not to say","height_cm":175,"baseline_weight_kg":80,"primary_goal":"weight loss","target_value":75,"target_unit":"kg","motivation":"Feel stronger","activity_level":"moderately active","dietary_preferences":"vegetarian","morning_time":"08:00","evening_time":"20:00"})
    add_log(user_id,"workout",{"active_minutes":45,"steps":6000},"Strength session")
    add_log(user_id,"journal",{"mood":8,"sleep_hours":7.5},"Good energy")
    result=report(user_id,30)
    assert result["summary"]["workout_days"] == 1
    assert result["summary"]["active_minutes"] == 45
    assert result["summary"]["journal_days"] == 1
