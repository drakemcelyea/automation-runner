from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.security.csrf import csrf_token_is_valid
from app.services.audit_service import write_audit_event


SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method.upper() not in SAFE_METHODS:
            if not csrf_token_is_valid(request):
                write_audit_event(
                    request=request,
                    action="security.csrf_failure",
                    outcome="failure",
                    actor_username=request.session.get("user"),
                    resource_type="http_request",
                    resource_id=request.url.path,
                    details={
                        "method": request.method.upper(),
                        "reason": "missing_or_invalid_csrf_token",
                    },
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "status": "error",
                        "message": "Invalid or missing CSRF token",
                    },
                    headers={"X-CSRF-Error": "1"},
                )

        return await call_next(request)
