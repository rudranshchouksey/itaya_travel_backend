from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.bookings.router import router as bookings_router
from app.modules.destinations.router import router as destinations_router
from app.modules.experiences.router import router as experiences_router
from app.modules.listings.router import router as listings_router
from app.modules.payments.router import router as payments_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.reviews.router import router as reviews_router
from app.modules.search.router import router as search_router
from app.modules.trips.router import router as trips_router
from app.modules.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(
    destinations_router, prefix="/destinations", tags=["Destinations"]
)
api_router.include_router(listings_router, prefix="/listings", tags=["Listings"])
api_router.include_router(
    experiences_router, prefix="/experiences", tags=["Experiences"]
)
api_router.include_router(trips_router, prefix="/trips", tags=["Trips"])
api_router.include_router(bookings_router, prefix="/bookings", tags=["Bookings"])
api_router.include_router(payments_router, prefix="/payments", tags=["Payments"])
api_router.include_router(reviews_router)
api_router.include_router(search_router)
api_router.include_router(recommendations_router)
api_router.include_router(ai_router)
