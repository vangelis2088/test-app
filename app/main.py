import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

MAX_TITLE = 280

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates")


def read_organizer_titles(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
    except FileNotFoundError:
        logger.warning("Topics file %s not found; no organizer topics loaded", path)
        return []
    titles = []
    for entry in entries:
        title = str(entry.get("title", "")).strip()
        if title and len(title) <= MAX_TITLE:
            titles.append(title)
        else:
            logger.warning("Skipping invalid organizer topic: %r", entry)
    return titles


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    titles = read_organizer_titles(os.environ.get("TOPICS_FILE", "data/topics.json"))
    db.load_organizer_topics(titles)
    yield


app = FastAPI(title="Voting App", lifespan=lifespan)


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
def create_topic(request: Request, title: str = Form(""), author: str = Form("")):
    title = title.strip()
    author = author.strip() or None
    error = None
    if not title:
        error = "Please enter a topic."
    elif len(title) > MAX_TITLE:
        error = f"Topics can be at most {MAX_TITLE} characters."

    if error is None:
        db.create_topic(title, author)

    return templates.TemplateResponse(
        request,
        "_topics.html",
        {"topics": db.list_topics(), "error": error},
        status_code=422 if error else 200,
    )
