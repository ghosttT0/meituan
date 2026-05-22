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
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))
