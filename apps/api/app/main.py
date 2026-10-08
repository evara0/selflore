from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from app.auth import router as auth_router
from app.routers.workspace import router as workspace_router
import psycopg
from fastapi.responses import JSONResponse


WEB_DIST_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"


class FrontendFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        request_path = scope["path"]
        if (
            request_path == "/api"
            or request_path.startswith("/api/")
            or "\\" in request_path
            or any(part in {".", ".."} for part in request_path.split("/"))
        ):
            raise HTTPException(status_code=404)

        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code != 404
                or request_path.startswith("/assets/")
                or Path(request_path).suffix
            ):
                raise
            return await super().get_response("index.html", scope)


def create_app(web_dist_dir: Path = WEB_DIST_DIR) -> FastAPI:
    app = FastAPI()

    app.include_router(auth_router)
    app.include_router(workspace_router)

    @app.exception_handler(psycopg.OperationalError)
    async def database_unavailable(request, exc):
        return JSONResponse(status_code=503, content={"detail": {"code": "database_unavailable", "message": "数据库暂不可用，请稍后重试"}})

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    if (web_dist_dir / "index.html").is_file():
        app.mount("/", FrontendFiles(directory=web_dist_dir, html=True), name="web")

    return app


app = create_app()
