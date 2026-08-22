from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter()


@router.get("/health/database", tags=["System"])
async def database_health_check(db: AsyncSession = Depends(get_db)):  # noqa: B008
    try:
        # Execute a simple query to check database connectivity
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection is healthy"}
    except Exception:  # noqa: BLE001
        # Log the error internally here if you have a logger
        # Do not expose raw database errors
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        )
