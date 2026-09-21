"""FastAPI Application Entry Point & Route Registry."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.routers import (
    applications,
    auth,
    batches,
    emails,
    gaps,
    health,
    insights,
    jobs,
    keys,
    linkedin,
    resumes,
    roles,
    runs,
    scout,
    tenants,
    tracker,
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
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net;"
    )
    return response


DASHBOARD_FILE = Path(__file__).resolve().parent.parent / "templates" / "dashboard.html"


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse, tags=["Dashboard"])
async def root_dashboard():
    """Serves the interactive CareerHarness test console."""
    if DASHBOARD_FILE.exists():
        return HTMLResponse(content=DASHBOARD_FILE.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="""
        <html>
            <body style="font-family:sans-serif; padding:2rem; background:#0b0f17; color:#fff;">
                <h1>CareerHarness API</h1>
                <p>Welcome! Explore API endpoints via <a style="color:#06b6d4;" href="/docs">Swagger UI</a>.</p>
            </body>
        </html>
        """
    )


# Mount API Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
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
app.include_router(tracker.router)
app.include_router(insights.router)
