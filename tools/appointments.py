from livekit.agents import function_tool, RunContext
from db.supabase import supabase


@function_tool
async def identify_user(context: RunContext):
    """Ask the user for their phone number."""
    return "Please tell me your Name and phone number to continue."


@function_tool
async def fetch_slots(context: RunContext):
    """
    Fetch available appointment slots. Call this when the user asks about availability.
    
    Returns available slots that you should present to the user in a friendly spoken format.
    Convert dates to natural speech (e.g., "February 10th at 3 PM").
    """
    # These are the available slots
    slots = [
        {"date": "2026-02-10", "time": "15:00", "display": "February 10th at 3 PM"},
        {"date": "2026-02-11", "time": "11:00", "display": "February 11th at 11 AM"},
        {"date": "2026-02-12", "time": "16:00", "display": "February 12th at 4 PM"},
    ]
    
    # Format for voice response
    slot_descriptions = [slot["display"] for slot in slots]
    
    return f"We have {len(slots)} available appointment slots: {', '.join(slot_descriptions[:-1])}, and {slot_descriptions[-1]}. Which time works best for you?"


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
