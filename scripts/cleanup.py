import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def run():
    db_url = os.getenv('DATABASE_URL').replace('+asyncpg', '')
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute('DROP TABLE IF EXISTS webhook_events, trips, trip_days, trip_destinations, trip_participants, trip_items, bookings, booking_guests, booking_items, payments, provider_transactions, refunds, reviews CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS trip_item_type_enum CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS tripitemtype CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS payment_status_enum CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS refund_status_enum CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS booking_status_enum CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS transaction_type_enum CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS transaction_status_enum CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS tripstatus CASCADE;')
        await conn.execute('DROP TYPE IF EXISTS tripparticipantrole CASCADE;')
        print("Cleanup successful")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
