"""FastAPI Application Entry Point & Route Registry."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    applications,
    batches,
    emails,
    gaps,
    health,
    jobs,
    keys,
    linkedin,
    resumes,
    roles,
    runs,
    scout,
    vault,
)
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


@app.middleware("http")
async def add_security_headers(request, call_next):
    """Sets standard security headers on all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Mount API Routers
app.include_router(health.router)
app.include_router(keys.router)
app.include_router(runs.router)
app.include_router(roles.router)
app.include_router(resumes.router)
app.include_router(linkedin.router)
app.include_router(gaps.router)
app.include_router(emails.router)
app.include_router(scout.router)
app.include_router(jobs.router)
app.include_router(batches.router)
app.include_router(vault.router)
app.include_router(applications.router)
