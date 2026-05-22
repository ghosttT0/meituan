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
