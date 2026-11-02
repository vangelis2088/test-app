import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.load_organizer_topics(os.environ.get("TOPICS_FILE", "data/topics.json"))
    yield


app = FastAPI(title="My Voting App", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"topics": db.list_topics()}
    )


@app.get("/topics", response_class=HTMLResponse)
def topics_partial(request: Request):
    return templates.TemplateResponse(
        request, "_topics.html", {"topics": db.list_topics()}
    )


@app.post("/topics", response_class=HTMLResponse)
def create_topic(request: Request, title: str = Form(""), name: str = Form("")):
    try:
        db.create_topic(title, name)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "_form_error.html",
            {"error": str(exc)},
            status_code=422,
            headers={"HX-Retarget": "#form-error", "HX-Reswap": "innerHTML"},
        )
    return templates.TemplateResponse(
        request, "_topics.html", {"topics": db.list_topics()}
    )
