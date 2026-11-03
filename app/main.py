import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

MAX_TITLE = 280
VOTER_COOKIE = "voter_id"
VOTER_ID_RE = re.compile(r"^[0-9a-f]{32}$")
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365

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


@app.middleware("http")
async def voter_cookie(request: Request, call_next):
    """Give each browser a random voter id; it only identifies the voter."""
    voter_id = request.cookies.get(VOTER_COOKIE, "")
    is_new = not VOTER_ID_RE.match(voter_id)
    if is_new:
        voter_id = uuid.uuid4().hex
    request.state.voter_id = voter_id
    response = await call_next(request)
    if is_new:
        response.set_cookie(
            VOTER_COOKIE,
            voter_id,
            max_age=VOTER_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
    return response


def render(request: Request, name: str, error: str | None = None, status_code=200):
    context = {
        "topics": db.list_topics(),
        "voted_topic_id": db.voted_topic_id(request.state.voter_id),
        "error": error,
    }
    return templates.TemplateResponse(request, name, context, status_code=status_code)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return render(request, "index.html")


@app.get("/topics", response_class=HTMLResponse)
def topics_partial(request: Request):
    return render(request, "_topics.html")


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

    return render(request, "_topics.html", error, status_code=422 if error else 200)


@app.post("/topics/{topic_id}/vote", response_class=HTMLResponse)
def vote(request: Request, topic_id: int):
    if not db.topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    db.cast_vote(request.state.voter_id, topic_id)
    return render(request, "_topics.html")
