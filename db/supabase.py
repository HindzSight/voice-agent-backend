from supabase import create_async_client
from config import SUPABASE_URL, SUPABASE_KEY
import asyncio

_supabase = None

async def get_supabase():
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        _supabase = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase
