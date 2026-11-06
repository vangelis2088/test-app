import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

VOTER_COOKIE = "voter_id"
VOTER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")  # secrets.token_urlsafe(16)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.load_organizer_topics(os.environ.get("TOPICS_FILE", "data/topics.json"))
    yield


app = FastAPI(title="Voting App", lifespan=lifespan)


@app.middleware("http")
async def assign_voter_id(request: Request, call_next):
    """Give every browser a random voter id cookie; it only identifies the voter."""
    voter_id = request.cookies.get(VOTER_COOKIE, "")
    is_new = not VOTER_ID_RE.match(voter_id)
    if is_new:
        voter_id = secrets.token_urlsafe(16)
    request.state.voter_id = voter_id
    response = await call_next(request)
    if is_new:
        response.set_cookie(
            VOTER_COOKIE,
            voter_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )
    return response


def render_topics(request: Request, template: str = "_topics.html", **context):
    context.setdefault("topics", db.list_topics())
    context.setdefault("voted_topic_id", db.voted_topic_id(request.state.voter_id))
    status_code = context.pop("status_code", 200)
    return templates.TemplateResponse(
        request, template, context, status_code=status_code
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return render_topics(request, "index.html")


@app.get("/topics", response_class=HTMLResponse)
def topics_partial(request: Request):
    return render_topics(request)


@app.post("/topics", response_class=HTMLResponse)
def create_topic(request: Request, title: str = Form(""), author: str = Form("")):
    try:
        clean_title = db.validate_title(title)
    except ValueError as e:
        return render_topics(request, error=str(e), status_code=422)
    db.create_topic(clean_title, author.strip() or None)
    return render_topics(request)


@app.post("/topics/{topic_id}/vote", response_class=HTMLResponse)
def vote(request: Request, topic_id: int):
    if not db.topic_exists(topic_id):
        return HTMLResponse("Topic not found", status_code=404)
    db.cast_vote(request.state.voter_id, topic_id)
    return render_topics(request)
