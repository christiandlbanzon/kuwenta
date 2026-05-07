import logging

from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.qa import QARequest, QAResponse
from app.services.qa import answer_question

router = APIRouter(prefix="/qa", tags=["qa"])
log = logging.getLogger("kuwenta.qa")


@router.post("", response_model=QAResponse)
async def ask(payload: QARequest, user: CurrentUser, session: SessionDep) -> QAResponse:
    """Natural-language Q&A over the user's transactions.

    The planner LLM picks one or more whitelisted tools; tools execute parameterized
    queries scoped to the current user; the summarizer LLM produces a peso-formatted
    prose answer. The full tool-call trace is returned alongside the answer for
    transparency.

    Errors are caught and returned as a graceful "I couldn't answer" response so the
    chat UI never sees a 500 — it shows the user a polite message instead.
    """
    try:
        return await answer_question(session, user, payload.question)
    except Exception:
        log.exception("Q&A failed")
        return QAResponse(
            answer=(
                "I ran into an issue answering that. Try rephrasing, or ask "
                'something specific like "how much did I spend on food this month?".'
            ),
            tool_calls=[],
            cannot_answer=True,
        )
