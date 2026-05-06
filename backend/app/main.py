"""FastAPI application entrypoint."""

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import accounts as accounts_api
from app.api import admin as admin_api
from app.api import auth as auth_api
from app.api import budgets as budgets_api
from app.api import categories as categories_api
from app.api import imports as imports_api
from app.api import insights as insights_api
from app.api import qa as qa_api
from app.api import receipts as receipts_api
from app.api import transactions as transactions_api

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Start APScheduler unless we're in a test/eval/CI context
    sched = None
    if os.getenv("KUWENTA_DISABLE_SCHEDULER", "0") != "1":
        from app.jobs.scheduler import start_scheduler

        try:
            sched = start_scheduler()
        except Exception:
            logging.exception("scheduler failed to start; continuing without it")
    yield
    if sched is not None:
        sched.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Kuwenta",
        description="AI-powered personal finance tracker for the Philippines",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_api.router)
    app.include_router(accounts_api.router)
    app.include_router(categories_api.router)
    app.include_router(transactions_api.router)
    app.include_router(budgets_api.router)
    app.include_router(receipts_api.router)
    app.include_router(imports_api.router)
    app.include_router(qa_api.router)
    app.include_router(insights_api.router)
    app.include_router(admin_api.router)

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
