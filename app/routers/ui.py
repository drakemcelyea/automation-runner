from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATE_DIR


templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
router = APIRouter(tags=["ui"])


@router.get("/ui", response_class=HTMLResponse)
def ui(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
