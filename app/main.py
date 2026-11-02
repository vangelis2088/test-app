import os
from contextlib import asynccontextmanager
from pathlib import Path
from sqlite3 import Connection
from typing import Annotated

from fastapi import Depends, FastAPI, Form, Request
from fastapi.templating import Jinja2Templates

from app import db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


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


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def index(request: Request, conn: Conn):
    return templates.TemplateResponse(
        request, "index.html", {"topics": db.list_topics(conn)}
    )


@app.get("/topics")
def topics_partial(request: Request, conn: Conn):
    return templates.TemplateResponse(
        request, "_topics.html", {"topics": db.list_topics(conn)}
    )


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
    return templates.TemplateResponse(
        request, "_topics.html", {"topics": db.list_topics(conn)}
    )
