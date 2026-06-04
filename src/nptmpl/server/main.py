import os
import secrets

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from pathlib import Path
from typing import Optional

from nptmpl.core.config import ConfigManager
from nptmpl.server.db import DatabaseManager
from nptmpl.server.api import router as api_router, download_router, inspect_router
from nptmpl.server.web import router as web_router
from nptmpl.server.routes.public import templates
from nptmpl.server.ui_utils import get_site_meta


def create_app(storage_path: Path, config: Optional[ConfigManager] = None) -> FastAPI:
    """Factory function to create the FastAPI application."""
    app = FastAPI(
        title="nptmpl Registry",
        description="Distributed CLI Template Manager Server",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )

    if config is None:
        config = ConfigManager()

    # Application state
    app.state.storage_path = storage_path
    app.state.db = DatabaseManager(storage_path / "registry.db")
    app.state.config = config

    # Middleware
    secret_key = os.environ.get("NPTMPL_SESSION_SECRET") or config.get_auth_token() or secrets.token_hex(32)
    app.add_middleware(SessionMiddleware, secret_key=secret_key)

    # Static files
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Routes
    app.include_router(api_router)
    app.include_router(download_router)
    app.include_router(inspect_router)
    app.include_router(web_router)

    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": str(exc.detail) if hasattr(exc, "detail") else "Not Found"}
            )
        return templates.TemplateResponse(request, "404.html", {
            "site_meta": get_site_meta(app.state.config)
        }, status_code=404)

    @app.exception_handler(401)
    async def unauthorized_exception_handler(request: Request, exc):
        if request.url.path.startswith("/api/"):
            headers = getattr(exc, "headers", {})
            return JSONResponse(
                status_code=401,
                content={"detail": str(exc.detail) if hasattr(exc, "detail") else "Unauthorized"},
                headers=headers
            )
        
        return RedirectResponse(url="/login?error=unauthorized")

    return app

def get_app_for_reload():
    """Entry point for uvicorn --reload."""
    storage = os.environ.get("NPTMPL_SERVER_STORAGE")
    config_path = os.environ.get("NPTMPL_CONFIG_PATH")
    
    if not storage:
        raise RuntimeError("NPTMPL_SERVER_STORAGE environment variable not set.")
        
    storage_path = Path(storage).resolve()
    config = ConfigManager(config_path)
    return create_app(storage_path, config)

def start_server(host: str, port: int, storage: str, 
                 reindex: bool = False, 
                 enable_docs: bool = False, 
                 reload: bool = False,
                 config: Optional[ConfigManager] = None):
    """Starts the FastAPI server with the specified configuration."""
    storage_path = Path(storage).resolve()
    storage_path.mkdir(parents=True, exist_ok=True)

    if config is None:
        config = ConfigManager()

    if reindex:
        from nptmpl.server.reindexer import ServerReindexer
        db = DatabaseManager(storage_path / "registry.db")
        ServerReindexer.reindex(storage_path, db)

    os.environ["NPTMPL_SERVER_STORAGE"] = str(storage_path)
    if config.config_file_used:
        os.environ["NPTMPL_CONFIG_PATH"] = str(config.config_file_used)

    print(f"🚀 Starting nptmpl Server on {host}:{port}")
    print(f"📂 Storage path: {storage_path}")
    
    if enable_docs:
        print(f"📖 API Documentation enabled at http://{host}:{port}/api/docs")
    else:
        print("🔒 API Documentation disabled (use --enable-docs to enable)")

    if reload:
        package_src = Path(__file__).parent.parent.parent
        uvicorn.run(
            "nptmpl.server.main:get_app_for_reload", 
            host=host, 
            port=port, 
            reload=True, 
            factory=True,
            reload_dirs=[str(package_src)]
        )
    else:
        app = create_app(storage_path, config=config)
        if not enable_docs:
            app.docs_url = None
            app.redoc_url = None
        uvicorn.run(app, host=host, port=port)
