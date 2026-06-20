import asyncio
from membrane.config import load_settings
from membrane.db import init_db, get_db

async def test_connection():
    settings = load_settings()
    print("Database URL:", settings.database_url)
    
    print("Initializing Database tables...")
    await init_db(settings.database_url)
    print("Database schema successfully created/verified!")
    
    print("Testing connection...")
    conn = await get_db(settings.database_url)
    try:
        row = await conn.fetchrow("SELECT 1 as result")
        print("Connection successful! Result:", row['result'])
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
