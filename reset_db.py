import asyncio
import asyncpg

async def run():
    # Use non-pooler URL
    conn = await asyncpg.connect("postgresql://neondb_owner:npg_Sh7Q4BLNgKnw@ep-lingering-hill-ax3853it.c-4.us-east-2.aws.neon.tech/neondb?ssl=require")
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await conn.close()
    print("Schema dropped and recreated successfully.")

asyncio.run(run())
