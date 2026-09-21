"""FastAPI Application Entry Point & Route Registry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health, keys, runs
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    if settings.ENVIRONMENT != "production":
        await init_db()
    yield


app = FastAPI(
    title="CareerHarness API",
    description="Standalone AI Career Agent Platform with BYOK economics and in-house thin harness",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health.router)
app.include_router(keys.router)
app.include_router(runs.router)
