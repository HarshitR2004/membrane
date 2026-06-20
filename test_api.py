import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://membrane-j09r.onrender.com/api/auth/connect",
            json={"wallet": "0x123", "signature": "sig", "message": "msg"},
            timeout=10.0
        )
        print(f"Status Code: {resp.status_code}")
        print(f"Response Body: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test())
