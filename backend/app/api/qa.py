from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.qa import QARequest, QAResponse
from app.services.qa import answer_question

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("", response_model=QAResponse)
async def ask(payload: QARequest, user: CurrentUser, session: SessionDep) -> QAResponse:
    """Natural-language Q&A over the user's transactions.

    The planner LLM picks one or more whitelisted tools; tools execute parameterized
    queries scoped to the current user; the summarizer LLM produces a peso-formatted
    prose answer. The full tool-call trace is returned alongside the answer for
    transparency.
    """
    return await answer_question(session, user, payload.question)
