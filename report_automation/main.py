from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from report_automation.env import bootstrap_local_environment
from report_automation.settings import ROOT_DIR


def _bootstrap_local_environment() -> None:
    bootstrap_local_environment(ROOT_DIR)


_bootstrap_local_environment()

from report_automation.api import frontend, generate, other_chapter1, other_proof, system


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system.router)
    app.include_router(other_proof.router)
    app.include_router(other_chapter1.router)
    app.include_router(generate.router)
    app.include_router(frontend.router)
    return app


app = create_app()
