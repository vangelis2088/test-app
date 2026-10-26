import os
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from app import db

templates = Jinja2Templates(directory="templates")
security = HTTPBasic(auto_error=False)


NO_STORE = {"Cache-Control": "no-store"}


def require_moderator(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> None:
    """Allow only requests with the ADMIN_PASSWORD; deny all if it is unset."""
    expected = os.environ.get("ADMIN_PASSWORD")
    if not expected:
        raise HTTPException(
            status_code=403, detail="Moderation is disabled", headers=NO_STORE
        )
    supplied = credentials.password if credentials else ""
    if credentials is None or not secrets.compare_digest(
        supplied.encode(), expected.encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="moderate"', **NO_STORE},
        )


def require_htmx(request: Request) -> None:
    """Reject state-changing requests lacking htmx's header (CSRF defence)."""
    if request.headers.get("HX-Request") != "true":
        raise HTTPException(
            status_code=403, detail="Missing HX-Request header", headers=NO_STORE
        )


router = APIRouter(dependencies=[Depends(require_moderator)])


def render(request: Request, name: str):
    return templates.TemplateResponse(
        request, name, {"topics": db.list_topics()}, headers=NO_STORE
    )


@router.get("/moderate")
def moderate_page(request: Request):
    return render(request, "moderate.html")


@router.post("/moderate/topics/{topic_id}/answer", dependencies=[Depends(require_htmx)])
def answer_topic(request: Request, topic_id: int):
    if not db.mark_answered(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return render(request, "_moderate_list.html")


@router.post("/moderate/topics/{topic_id}/delete", dependencies=[Depends(require_htmx)])
def delete_topic(request: Request, topic_id: int):
    if not db.delete_topic(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found")
    return render(request, "_moderate_list.html")
