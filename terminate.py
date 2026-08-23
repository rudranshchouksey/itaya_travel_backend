import asyncio
import asyncpg

async def run():
    conn = await asyncpg.connect("postgresql://neondb_owner:npg_Sh7Q4BLNgKnw@ep-lingering-hill-ax3853it.c-4.us-east-2.aws.neon.tech/neondb?ssl=require")
    await conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'neondb' AND pid != pg_backend_pid();")
    await conn.close()

asyncio.run(run())
