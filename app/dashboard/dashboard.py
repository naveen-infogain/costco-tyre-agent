"""
Dashboard router — FastAPI routes for /dashboard and /dashboard/api.
"""
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.dashboard.analytics_store import get_full_analytics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_DASH_STATIC = Path(__file__).parent / "static"
_DASH_STATIC.mkdir(exist_ok=True)


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
async def serve_dashboard():
    html = _DASH_STATIC / "dashboard.html"
    if html.exists():
        return FileResponse(str(html))
    return JSONResponse({"message": "Dashboard UI not yet built — run Phase 7"}, status_code=503)


@router.get("/api")
async def dashboard_api():
    """Return full analytics JSON for the live dashboard."""
    return get_full_analytics()
