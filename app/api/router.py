from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.destinations.router import router as destinations_router
from app.modules.listings.router import router as listings_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(
    destinations_router, prefix="/destinations", tags=["Destinations"]
)
api_router.include_router(
    listings_router, prefix="/listings", tags=["Listings"]
)
