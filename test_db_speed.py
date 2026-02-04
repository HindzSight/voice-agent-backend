import asyncio
import time
from db.supabase import get_supabase
from dotenv import load_dotenv

load_dotenv()

async def test_speed():
    try:
        start = time.time()
        supabase = await get_supabase()
        setup_time = time.time() - start
        print(f"Client setup time: {setup_time:.4f}s")

        start = time.time()
        # Simple query
        res = await supabase.table("slots").select("*").limit(1).execute()
        query_time = time.time() - start
        print(f"Simple query time: {query_time:.4f}s")
        print(f"Result count: {len(res.data)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_speed())
