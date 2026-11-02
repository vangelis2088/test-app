import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from sqlite3 import Connection
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app import db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)

VOTER_COOKIE = "voter_id"
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
VOTER_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = os.environ.get("QA_DB_PATH", "qa.db")
    topics_file = os.environ.get("TOPICS_FILE", "data/topics.json")
    conn = db.connect(db_path)
    try:
        db.init_db(conn)
        db.load_organizer_topics(conn, topics_file)
    finally:
        conn.close()
    app.state.db_path = db_path
    yield


app = FastAPI(title="My Voting App", lifespan=lifespan)


def get_conn(request: Request):
    conn = db.connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[Connection, Depends(get_conn)]


@app.middleware("http")
async def voter_cookie(request: Request, call_next):
    """Give each browser a random voter id; it only identifies, never counts."""
    voter_id = request.cookies.get(VOTER_COOKIE, "")
    is_new = not VOTER_ID_RE.fullmatch(voter_id)
    if is_new:
        voter_id = secrets.token_hex(16)
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


def render_topics(request: Request, conn: Connection, template: str = "_topics.html"):
    return templates.TemplateResponse(
        request,
        template,
        {
            "topics": db.list_topics(conn),
            "voted_topic_id": db.get_voted_topic_id(conn, request.state.voter_id),
        },
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def index(request: Request, conn: Conn):
    return render_topics(request, conn, "index.html")


@app.get("/topics")
def topics_partial(request: Request, conn: Conn):
    return render_topics(request, conn)


@app.post("/topics")
def create_topic(
    request: Request,
    conn: Conn,
    title: Annotated[str, Form()] = "",
    author: Annotated[str, Form()] = "",
):
    title = title.strip()
    author = author.strip()
    error = None
    if not title:
        error = "Please enter a topic."
    elif len(title) > db.MAX_TITLE_LENGTH:
        error = f"Topics can be at most {db.MAX_TITLE_LENGTH} characters."
    if error:
        return templates.TemplateResponse(
            request,
            "_form_error.html",
            {"error": error},
            status_code=422,
            headers={"HX-Retarget": "#form-error", "HX-Reswap": "innerHTML"},
        )
    db.create_topic(conn, title, author or None)
    return render_topics(request, conn)


@app.post("/topics/{topic_id}/vote")
def vote(request: Request, conn: Conn, topic_id: int):
    if not db.cast_vote(conn, request.state.voter_id, topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return render_topics(request, conn)
