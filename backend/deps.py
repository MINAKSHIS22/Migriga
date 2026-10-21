# MIGRIGA Shared FastAPI dependencies (session-token authentication & admin authorization)
from typing import Optional

from fastapi import Depends, Header, HTTPException

from backend.database import get_db


def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.email, u.full_name, u.phone, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def require_admin(user: Optional[dict] = Depends(get_current_user)):
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user
