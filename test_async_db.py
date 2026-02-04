import asyncio
from db.supabase import get_supabase

async def test_db():
    print("Testing async connection to Supabase...")
    supabase = await get_supabase()
    try:
        # Check appointments table
        res = await supabase.table("appointments").select("*").limit(1).execute()
        print(f"Successfully connected to Supabase. Appointments data: {res.data}")
    except Exception as e:
        print(f"Error accessing 'appointments' table: {e}")

    try:
        # Check call_summaries table
        res = await supabase.table("call_summaries").select("*").limit(1).execute()
        print(f"Call summaries data: {res.data}")
    except Exception as e:
        print(f"Error accessing 'call_summaries' table: {e}")

    try:
        # Check slots table
        res = await supabase.table("slots").select("*").limit(5).execute()
        print(f"Slots data: {res.data}")
    except Exception as e:
        print(f"Error accessing 'slots' table: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
