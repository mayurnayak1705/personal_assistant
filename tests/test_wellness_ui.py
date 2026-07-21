from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_wellness_ui_uses_chat_for_setup_and_modal_for_visuals_only():
    html=(ROOT/"templates/index.html").read_text()
    script=(ROOT/"static/js/app.js").read_text()
    assert 'id="wellnessSetup"' not in html
    assert 'id="wellnessLogForm"' not in html
    assert 'id="wellnessStart"' in html
    assert 'id="wellnessReport"' in html
    assert 'Start my wellness setup.' in script
    assert '/api/wellness/report' in script
    assert 'goal proximity' in script


def test_wellness_prompt_defines_conversational_onboarding_and_usage_guide():
    planner=(ROOT/"app/agents/planner.py").read_text()
    assert "never direct the user to a form" in planner
    assert "Ask only one concise question at a time" in planner
    assert "do not ask the user to choose a tracking category" in planner
    assert "top wellness heart button opens visual graphs" in planner
