from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
TEMPLATE_PATH = WEB_DIR / "templates" / "demo.html"
STATIC_DIR = WEB_DIR / "static"

router = APIRouter(tags=["demo"])
demo_static = StaticFiles(directory=str(STATIC_DIR))


@router.get("/demo", response_class=HTMLResponse)
def demo_page() -> HTMLResponse:
    css_version = int((STATIC_DIR / "demo.css").stat().st_mtime)
    js_version = int((STATIC_DIR / "demo-view.js").stat().st_mtime)
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("/demo/assets/demo.css", f"/demo/assets/demo.css?v={css_version}")
    html = html.replace("/demo/assets/demo-view.js", f"/demo/assets/demo-view.js?v={js_version}")
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )
