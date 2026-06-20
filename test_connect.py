import asyncio
import asyncpg
from membrane.config import load_settings
from membrane.api.services import AuthService

async def test():
    settings = load_settings()
    db = await asyncpg.connect(settings.database_url)
    try:
        user, is_first = await AuthService.connect_wallet(db, '0x123456789', 'sig', 'msg')
        print("Success:", user, is_first)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(test())
