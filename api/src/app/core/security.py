from fastapi import Header, HTTPException

def require_admin(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = authorization.split(" ", 1)[1]
    from .config import settings
    if token != settings.ADMIN_TOKEN:
        raise HTTPException(401, "Unauthorized")
