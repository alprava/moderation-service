from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


def register_exception_handlers(app):
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        # Если ошибка уже в формате {code, message} — оставляем
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )
        # Иначе преобразуем в стандартный формат
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": "ERROR", "message": str(exc.detail)},
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": str(exc)},
        )
