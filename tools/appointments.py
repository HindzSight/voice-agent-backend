from livekit.agents import function_tool, RunContext
from db.supabase import supabase


@function_tool
async def identify_user(context: RunContext):
    """Ask the user for their phone number."""
    return "Please tell me your Name and phone number to continue."


@function_tool
async def fetch_slots(context: RunContext):
    """
    Fetch available appointment slots.
    
    Returns a list of available slots in 'YYYY-MM-DD HH:MM' format.
    Tell the user these slots when they ask about availability.
    """
    slots = [
        "2026-02-10 15:00",
        "2026-02-11 11:00",
        "2026-02-12 16:00",
    ]
    # Return as a formatted string for the LLM to speak
    return f"Available slots are: {', '.join(slots)}"


@function_tool
async def book_appointment(
    context: RunContext,
    date: str,
    time: str,
    contact_number: str,
    name: str,
):
    """
    Book an appointment for the user.
    
    Args:
        date: The appointment date in YYYY-MM-DD format (e.g., '2026-02-10')
        time: The appointment time in HH:MM format (e.g., '15:00')
        contact_number: The user's phone number
        name: The user's name
    """
    # Normalize date format if needed (convert DD-MM-YYYY to YYYY-MM-DD)
    if date and len(date) == 10 and date[2] == '-' and date[5] == '-':
        # Input is DD-MM-YYYY, convert to YYYY-MM-DD
        parts = date.split('-')
        if len(parts) == 3:
            date = f"{parts[2]}-{parts[1]}-{parts[0]}"
    
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
    """
    Modify appointment date or time.
    
    Args:
        appointment_id: The ID of the appointment to modify
        new_date: The new date in YYYY-MM-DD format (e.g., '2026-02-10')
        new_time: The new time in HH:MM format (e.g., '15:00')
    """
    # Normalize date format if needed (convert DD-MM-YYYY to YYYY-MM-DD)
    if new_date and len(new_date) == 10 and new_date[2] == '-' and new_date[5] == '-':
        parts = new_date.split('-')
        if len(parts) == 3:
            new_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
    
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
