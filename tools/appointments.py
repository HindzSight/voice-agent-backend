from livekit.agents import function_tool, RunContext
from db.supabase import supabase


@function_tool
async def identify_user(context: RunContext):
    """Ask the user for their phone number."""
    return "Please tell me your Name and phone number to continue."


@function_tool
async def fetch_slots(context: RunContext):
    """Fetch available appointment slots."""
    return [
        "2026-02-10 15:00",
        "2026-02-11 11:00",
        "2026-02-12 16:00",
    ]


@function_tool
async def book_appointment(
    context: RunContext,
    date: str,
    time: str,
    contact_number: str,
    name: str,
):
    """Book an appointment for the user."""
    conflict = (
        supabase.table("appointments")
        .select("*")
        .eq("date", date)
        .eq("time", time)
        .eq("status", "booked")
        .execute()
    )

    if conflict.data:
        return "That slot is already booked. Please choose another time."

    supabase.table("appointments").insert({
        "contact_number": contact_number,
        "date": date,
        "time": time,
        "status": "booked",
        "name": name,
    }).execute()

    return f"Your appointment is booked for {date} at {time}."


@function_tool
async def retrieve_appointments(
    context: RunContext,
    contact_number: str,
):
    """Retrieve past appointments for a user."""
    res = (
        supabase.table("appointments")
        .select("*")
        .eq("contact_number", contact_number)
        .execute()
    )

    if not res.data:
        return "You have no appointments."

    return res.data


@function_tool
async def cancel_appointment(
    context: RunContext,
    appointment_id: str,
):
    """Cancel an appointment."""
    supabase.table("appointments") \
        .update({"status": "cancelled"}) \
        .eq("id", appointment_id) \
        .execute()

    return "Your appointment has been cancelled."


@function_tool
async def modify_appointment(
    context: RunContext,
    appointment_id: str,
    new_date: str,
    new_time: str,
):
    """Modify appointment date or time."""
    conflict = (
        supabase.table("appointments")
        .select("*")
        .eq("date", new_date)
        .eq("time", new_time)
        .eq("status", "booked")
        .execute()
    )

    if conflict.data:
        return "That new slot is already booked."

    supabase.table("appointments") \
        .update({"date": new_date, "time": new_time}) \
        .eq("id", appointment_id) \
        .execute()

    return f"Your appointment has been moved to {new_date} at {new_time}."
