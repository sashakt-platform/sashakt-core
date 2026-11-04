import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class StripTrailingSlashMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope["path"]
            if len(path) > 1 and path.endswith("/"):
                stripped = path.rstrip("/") or "/"
                logger.info(
                    "Legacy trailing-slash request: %s %s", scope["method"], path
                )
                scope = dict(scope)
                scope["path"] = stripped
                raw_path = scope.get("raw_path")
                if raw_path:
                    scope["raw_path"] = raw_path.rstrip(b"/") or b"/"
        await self.app(scope, receive, send)
