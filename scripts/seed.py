import asyncio
import logging
import argparse

from app.core.database import AsyncSessionLocal
from scripts.seed_data.amenities import seed_amenities
from scripts.seed_data.users import seed_users, clean_demo_users
from scripts.seed_data.destinations import seed_destinations, clean_demo_destinations
from scripts.seed_data.listings import seed_listings, clean_demo_listings
from scripts.seed_data.experiences import seed_experiences, clean_demo_experiences
from scripts.seed_data.trips import seed_trips, clean_demo_trips
from scripts.seed_data.bookings import seed_bookings, clean_demo_bookings
from scripts.seed_data.payments import seed_payments, clean_demo_payments
from scripts.seed_data.reviews import seed_reviews

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def reset_demo_data():
    """Wipes only explicitly marked demo data."""
    logger.info("Starting demo data reset...")
    async with AsyncSessionLocal() as session:
        # Respect foreign key cascading. Order of deletion generally doesn't matter for cascades, 
        # but let's do it cleanly from children to parents to be safe or rely on CASCADE where configured.
        
        await clean_demo_payments(session)
        await clean_demo_bookings(session)
        await clean_demo_trips(session)
        await clean_demo_listings(session)
        await clean_demo_experiences(session)
        await clean_demo_destinations(session)
        await clean_demo_users(session)
        
        logger.info("Demo data reset complete.")

async def run_seed():
    """Runs the idempotent seed process."""
    logger.info("Starting database seed...")
    async with AsyncSessionLocal() as session:
        
        # 1. Base Reference Data
        await seed_amenities(session)
        
        # 2. Users (Providers & Travelers)
        users = await seed_users(session)
        travelers = users["travelers"]
        providers = users["providers"]
        
        # 3. Destinations
        destinations = await seed_destinations(session)
        
        # 4. Offerings
        listings = await seed_listings(session, providers, destinations)
        experiences = await seed_experiences(session, providers, destinations)
        
        # 5. Workflows
        await seed_trips(session, travelers, destinations, listings, experiences)
        bookings = await seed_bookings(session, travelers, listings, experiences)
        
        # 6. Financials & Reviews
        await seed_payments(session, bookings)
        await seed_reviews(session, bookings)
        
        logger.info("Database seeding complete!")
        print("\n--- SEED SUMMARY ---")
        print(f"Users (Travelers/Providers): {len(travelers)} / {len(providers)}")
        print(f"Destinations: {len(destinations)}")
        print(f"Listings: {len(listings)}")
        print(f"Experiences: {len(experiences)}")
        print(f"Bookings: {len(bookings)}")
        print("---------------------\n")

def main():
    parser = argparse.ArgumentParser(description="Database Seeding Tool")
    parser.add_argument("--reset-demo", action="store_true", help="Delete all explicitly marked demo data before seeding.")
    args = parser.parse_args()
    
    if args.reset_demo:
        asyncio.run(reset_demo_data())
    else:
        asyncio.run(run_seed())

if __name__ == "__main__":
    main()
