# Database Seeding

This project uses a deterministic data seeding system designed for realistic mock data populating directly into PostgreSQL.

## Why Database Seeding?
Instead of hardcoding mocks in FastAPI endpoints or serving static JSON files, the website and mobile application need a realistic representation of data traversing actual endpoints with proper latency, pagination, and relational constraints.

## Approach
- **Idempotency**: All seeding scripts use a deterministic UUID approach. Running the script multiple times will not create duplicates.
- **Relational Integrity**: Seeds insert entities in a specific order to satisfy all Foreign Keys (`users` -> `destinations` -> `amenities` -> `listings` / `experiences` -> `trips` -> `bookings` -> `payments` -> `reviews`).
- **Domain Focus**: Data represents Indian and International stays/experiences matching the platform domain.
- **Demo Scope**: All generated users have emails ending in `@demo.itvaya.com`.

## Usage
Run the following from the `backend` root:

```bash
# Set your environment variables in .env
# To run the seed script:
python -m scripts.seed

# To clear ONLY demo data (leaves actual users/data intact):
python -m scripts.seed --reset-demo
```

## Structure
All scripts are located in `scripts/seed_data/`:
- `amenities.py`: Core feature lists.
- `users.py`: Mock travelers and providers with a fixed `password123`.
- `destinations.py`: Top-tier cities/regions.
- `listings.py`: Accommodations (hotels, homestays).
- `experiences.py`: Treks, tours, local activities.
- `trips.py`: Multi-day itineraries.
- `bookings.py`: Transaction records bridging users, listings, and trips.
- `payments.py`: Processed transactions and refund examples.
- `reviews.py`: User generated ratings.

All modules expose an idempotent `seed_*` method and a `clean_*` method for the `--reset-demo` execution.
