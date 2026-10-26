import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from .ai.provider import ai_configured
from .config import ROOT, settings
from .errors import register_handlers
from .routes import auth, books, tickets
from .seed import seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bookleaf")


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_if_empty()  # pre-seed the live demo with the provided dataset on first boot
    log.info("AI: %s", f"enabled ({settings.ai_provider})" if ai_configured() else "NO API KEY: using rule-based fallbacks")
    yield


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Content-Security-Policy": ("default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'"),
        })
        return resp


def create_app() -> FastAPI:
    # OpenAPI/Swagger docs are served at /api/docs (API documentation deliverable).
    app = FastAPI(title="BookLeaf Author Support Portal API", version="1.0.0",
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json", lifespan=lifespan)
    register_handlers(app)
    app.add_middleware(SecurityHeaders)
    if settings.cors_origin:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin.split(","), allow_headers=["*"], allow_methods=["*"])

    api = APIRouter(prefix="/api")
    api.include_router(auth.router, tags=["auth"])
    api.include_router(books.router, tags=["books"])
    api.include_router(tickets.router, tags=["tickets & admin"])
    app.include_router(api)

    # Serve the built React client (single-service deployment). client/dist is pre-built and included.
    dist = ROOT / "client" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"error": {"code": "NOT_FOUND", "message": f"No route for /{path}"}}, status_code=404)
            f = (dist / path).resolve()
            if path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")
    return app


app = create_app()
