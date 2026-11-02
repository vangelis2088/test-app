import os
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import db

VOTER_COOKIE = "voter_id"
VOTER_ID_RE = re.compile(r"[0-9a-f]{32}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.load_organizer_topics(os.environ.get("TOPICS_FILE", "data/topics.json"))
    yield


app = FastAPI(title="My Voting App", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.middleware("http")
async def assign_voter_id(request: Request, call_next):
    voter_id = request.cookies.get(VOTER_COOKIE, "")
    is_new = not VOTER_ID_RE.fullmatch(voter_id)
    if is_new:
        voter_id = uuid.uuid4().hex
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


def _topics_context(request: Request) -> dict:
    return {
        "topics": db.list_topics(),
        "voted_topic_id": db.voted_topic_id(request.state.voter_id),
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _topics_context(request))


@app.get("/topics", response_class=HTMLResponse)
def topics_partial(request: Request):
    return templates.TemplateResponse(request, "_topics.html", _topics_context(request))


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
    return templates.TemplateResponse(request, "_topics.html", _topics_context(request))


@app.post("/topics/{topic_id}/vote", response_class=HTMLResponse)
def vote(request: Request, topic_id: int):
    try:
        db.cast_vote(request.state.voter_id, topic_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Topic not found")
    return templates.TemplateResponse(request, "_topics.html", _topics_context(request))
