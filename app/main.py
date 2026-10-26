import re
import uuid
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app import db, export, moderation

templates = Jinja2Templates(directory="templates")

VOTER_COOKIE = "voter_id"
VOTER_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.load_organizer_topics()
    yield


app = FastAPI(title="My Voting App", lifespan=lifespan)
app.include_router(moderation.router)
app.include_router(export.router)


def render(request, name, voter_id, is_new_voter, error=None, status_code=200):
    response = templates.TemplateResponse(
        request,
        name,
        {"topics": db.list_topics(voter_id), "error": error},
        status_code=status_code,
    )
    if is_new_voter:
        response.set_cookie(
            VOTER_COOKIE,
            voter_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="lax",
        )
    return response


def resolve_voter(cookie_value: str | None) -> tuple[str, bool]:
    """Return (voter_id, is_new); malformed or missing cookies get a fresh id."""
    if cookie_value and VOTER_ID_RE.match(cookie_value):
        return cookie_value, False
    return uuid.uuid4().hex, True


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def index(request: Request, voter_id: str | None = Cookie(None)):
    voter, is_new = resolve_voter(voter_id)
    return render(request, "index.html", voter, is_new)


@app.get("/topics")
def topics_partial(request: Request, voter_id: str | None = Cookie(None)):
    voter, is_new = resolve_voter(voter_id)
    return render(request, "_topics.html", voter, is_new)


@app.post("/topics")
def create_topic(
    request: Request,
    title: str = Form(""),
    author: str = Form(""),
    voter_id: str | None = Cookie(None),
):
    voter, is_new = resolve_voter(voter_id)
    title = title.strip()
    author = author.strip() or None
    error = None
    if not title:
        error = "Please enter a topic."
    elif len(title) > db.MAX_TITLE_LEN:
        error = f"Topics are limited to {db.MAX_TITLE_LEN} characters."
    if error is None:
        db.add_topic(title, author)
    return render(
        request,
        "_topics.html",
        voter,
        is_new,
        error=error,
        status_code=422 if error else 200,
    )


@app.post("/topics/{topic_id}/vote")
def vote(request: Request, topic_id: int, voter_id: str | None = Cookie(None)):
    voter, is_new = resolve_voter(voter_id)
    if not db.cast_vote(voter, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return render(request, "_topics.html", voter, is_new)
