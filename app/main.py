import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

VOTER_COOKIE = "voter_id"
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def get_voter(request: Request) -> tuple[str, bool]:
    """Return (voter_id, is_new), minting a fresh id if the cookie is missing or malformed."""
    raw = request.cookies.get(VOTER_COOKIE)
    try:
        return str(uuid.UUID(raw)), False
    except (TypeError, ValueError):
        return str(uuid.uuid4()), True


def render(request: Request, name: str, context: dict, voter=None, **kwargs):
    """Render a template with the voter's current vote, issuing a voter cookie if needed."""
    voter_id, is_new = voter or get_voter(request)
    context = {"topics": db.list_topics(), "my_vote": db.get_vote(voter_id), **context}
    response = templates.TemplateResponse(request, name, context, **kwargs)
    if is_new:
        response.set_cookie(
            VOTER_COOKIE,
            voter_id,
            max_age=VOTER_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.load_organizer_topics(os.environ.get("TOPICS_FILE", "data/topics.json"))
    yield


app = FastAPI(title="Voting App", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return render(request, "index.html", {"max_title_length": db.MAX_TITLE_LENGTH})


@app.get("/topics", response_class=HTMLResponse)
def topics_partial(request: Request):
    return render(request, "_topics.html", {})


@app.post("/topics", response_class=HTMLResponse)
def create_topic(
    request: Request,
    title: Annotated[str, Form()] = "",
    author: Annotated[str, Form()] = "",
):
    title = title.strip()
    author = author.strip() or None
    if not db.is_valid_title(title):
        message = (
            "Please enter a topic."
            if not title
            else f"Topics can be at most {db.MAX_TITLE_LENGTH} characters."
        )
        return templates.TemplateResponse(
            request,
            "_form_error.html",
            {"message": message},
            status_code=422,
            headers={"HX-Retarget": "#form-error", "HX-Reswap": "innerHTML"},
        )
    db.add_topic(title, author)
    return render(request, "_topics.html", {})


@app.post("/topics/{topic_id}/vote", response_class=HTMLResponse)
def vote(request: Request, topic_id: int):
    voter = get_voter(request)
    if not db.cast_vote(voter[0], topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return render(request, "_topics.html", {}, voter=voter)
