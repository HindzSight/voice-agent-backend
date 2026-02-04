import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Missing Supabase credentials")
    exit(1)

supabase = create_client(url, key)

try:
    # Check appointments table
    res = supabase.table("appointments").select("*").limit(1).execute()
    print("Successfully connected to Supabase.")
    print(f"Appointments data: {res.data}")
except Exception as e:
    print(f"Error connecting to Supabase or accessing 'appointments' table: {e}")

try:
    # Check call_summaries table
    res = supabase.table("call_summaries").select("*").limit(1).execute()
    print(f"Call summaries data: {res.data}")
except Exception as e:
    print(f"Error accessing 'call_summaries' table: {e}")

try:
    # Check slots table
    res = supabase.table("slots").select("*").limit(5).execute()
    print(f"Slots data: {res.data}")
except Exception as e:
    print(f"Error accessing 'slots' table: {e}")
