import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


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
    return templates.TemplateResponse(
        request,
        "index.html",
        {"topics": db.list_topics(), "max_title_length": db.MAX_TITLE_LENGTH},
    )


@app.get("/topics", response_class=HTMLResponse)
def topics_partial(request: Request):
    return templates.TemplateResponse(
        request, "_topics.html", {"topics": db.list_topics()}
    )


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
    return templates.TemplateResponse(
        request, "_topics.html", {"topics": db.list_topics()}
    )
