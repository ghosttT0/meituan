from fastapi.testclient import TestClient

from app.main import app


def test_demo_page_and_assets_are_available() -> None:
    client = TestClient(app)

    page = client.get("/demo")
    css = client.get("/demo/assets/demo.css")
    script = client.get("/demo/assets/demo-view.js")

    assert page.status_code == 200
    assert 'id="demo-root"' in page.text
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


def test_demo_page_contains_dashboard_shell_and_accordions() -> None:
    client = TestClient(app)

    response = client.get("/demo")
    html = response.text

    for token in [
        "履约数字人外呼评估驾驶舱",
        "任务指令遵循自动评测演示",
        'id="demo-header"',
        'id="demo-input-panel"',
        'id="demo-summary-panel"',
        'id="scorecard-grid"',
        'data-accordion="evidence"',
        'data-accordion="rules"',
        'data-accordion="judge"',
        'data-accordion="raw-json"',
    ]:
        assert token in html


def test_demo_styles_include_responsive_dashboard_rules() -> None:
    client = TestClient(app)

    css = client.get("/demo/assets/demo.css").text

    assert ".demo-shell" in css
    assert "grid-template-columns: 400px minmax(0, 1fr);" in css
    assert "@media (max-width: 1100px)" in css
    assert "--primary: #38bdf8;" in css
