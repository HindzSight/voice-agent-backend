from livekit.agents import function_tool, RunContext
from db.supabase import get_supabase
from typing import Optional
import json
import logging
import asyncio

logger = logging.getLogger("tools.appointments")


async def _publish_tool_event(context: RunContext, payload: dict) -> None:
    room = context.session.userdata.get("room") if context and context.session else None
    if not room:
        return
    try:
        await room.local_participant.publish_data(
            json.dumps(payload), reliable=True, topic="tooling"
        )
    except Exception as e:
        logger.debug(f"Failed to publish tool event: {e}")


def _normalize_phone_number(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return raw
    text = raw.lower().strip()
    word_map = {
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "oh": "0",
    }
    parts = text.replace("-", " ").replace(",", " ").split()
    digits = []
    for part in parts:
        if part.isdigit():
            digits.append(part)
            continue
        if part in word_map:
            digits.append(word_map[part])
            continue
        filtered = "".join(ch for ch in part if ch.isdigit())
        if filtered:
            digits.append(filtered)
    if not digits:
        return raw
    return "".join(digits)


@function_tool
async def identify_user(context: RunContext):
    """Ask the user for their phone number."""
    message = "Please tell me your Name and phone number to continue."
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "identify_user",
            "args": {},
            "result": message,
        },
    )
    return message


@function_tool
async def fetch_slots(context: RunContext, date: Optional[str] = None):
    """
    Fetch available appointment slots from the database. Call this when the user asks about availability.

    If a date is provided, it will filter slots for that specific date.

    Returns available slots that you should present to the user in a friendly spoken format.
    Convert dates to natural speech (e.g., "February 10th at 3 PM").
    """
    logger.info(f"fetch_slots called with date={date}")
    await _publish_tool_event(
        context,
        {"type": "tool_call", "name": "fetch_slots", "args": {"date": date}},
    )
    try:
        logger.debug("Getting Supabase client...")
        supabase = await get_supabase()
        logger.debug("Supabase client obtained.")

        query = supabase.table("slots").select("*").eq("is_booked", False)

        if date:
            logger.debug(f"Filtering by date: {date}")
            query = query.eq("date", date)

        logger.debug("Executing query...")
        res = await query.order("date").order("time").execute()
        logger.debug(f"Query executed. Found {len(res.data)} slots.")

        if not res.data:
            if date:
                result = (
                    f"I'm sorry, there are no available slots for {date}. "
                    "Would you like to check another day?"
                )
            else:
                result = (
                    "I'm sorry, there are currently no available appointment slots. "
                    "Please check back later."
                )
            await _publish_tool_event(
                context,
                {
                    "type": "tool_call",
                    "name": "fetch_slots",
                    "args": {"date": date},
                    "result": result,
                },
            )
            return result

        slot_descriptions = [slot["display"] for slot in res.data] # type: ignore

        if len(slot_descriptions) == 1:
            result = f"We have one available slot: {slot_descriptions[0]}. Does that work for you?"
            await _publish_tool_event(
                context,
                {
                    "type": "tool_call",
                    "name": "fetch_slots",
                    "args": {"date": date},
                    "result": result,
                },
            )
            return result

        response = (
            f"We have {len(slot_descriptions)} available appointment slots: "
            f"{', '.join(slot_descriptions[:-1])}, and {slot_descriptions[-1]}. "  # type: ignore
            "Which time works best for you?"
        )
        logger.info(f"fetch_slots returning: {response}")
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "fetch_slots",
                "args": {"date": date},
                "result": response,
            },
        )
        return response

    except Exception as e:
        logger.error(f"Error fetching slots from Supabase: {e}", exc_info=True)
        result = (
            "I'm sorry, I encountered a technical error while checking for available slots. "
            "Please try again in a moment."
        )
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "fetch_slots",
                "args": {"date": date},
                "result": result,
            },
        )
        return result


@function_tool
async def book_appointment(
    context: RunContext,
    date: str,
    time: str,
    phone_number: str,
    name: str,
):
    """Book an appointment for the user."""
    normalized_phone = _normalize_phone_number(phone_number) or phone_number
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "book_appointment",
            "args": {
                "date": date,
                "time": time,
                "phone_number": normalized_phone,
                "name": name,
            },
        },
    )
    supabase = await get_supabase()

    if date and len(date) == 10 and date[2] == "-" and date[5] == "-":
        parts = date.split("-")
        if len(parts) == 3:
            date = f"{parts[2]}-{parts[1]}-{parts[0]}"

    slot_query = (
        supabase.table("slots")
        .select("*")
        .eq("date", date)
        .eq("time", time)
        .eq("is_booked", False)
    )

    conflict_query = (
        supabase.table("appointments")
        .select("*")
        .eq("date", date)
        .eq("time", time)
        .eq("status", "booked")
    )

    # Run checks in parallel
    logger.debug(f"Checking availability for {date} {time}...")
    try:
        # 5 second timeout for the checks
        slot_check, conflict = await asyncio.wait_for(
            asyncio.gather(slot_query.execute(), conflict_query.execute()),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        result = "I'm having trouble checking the schedule right now. Please try again."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "book_appointment",
                "args": {"date": date, "time": time, "phone_number": normalized_phone, "name": name},
                "result": result,
            },
        )
        return result

    if not slot_check.data:
        result = "I'm sorry, that slot is no longer available. Please pick another time from the available slots."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "book_appointment",
                "args": {"date": date, "time": time, "phone_number": normalized_phone, "name": name},
                "result": result,
            },
        )
        return result

    if conflict.data:
        logger.warning(f"Conflict found for booking: {date} {time}")
        result = "That slot is already booked. Please choose another time."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "book_appointment",
                "args": {"date": date, "time": time, "phone_number": normalized_phone, "name": name},
                "result": result,
            },
        )
        return result

    try:
        await supabase.table("slots").update({"is_booked": True}).eq("date", date).eq("time", time).execute()

        res = await supabase.table("appointments").insert({
            "contact_number": normalized_phone,
            "date": date,
            "time": time,
            "status": "booked",
            "name": name,
        }).execute()
        logger.info(f"Successfully booked appointment: {res.data}")
    except Exception as e:
        logger.error(f"Error inserting appointment into Supabase: {e}")
        result = "I'm sorry, I encountered a technical error while saving your appointment. Please try again in a moment."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "book_appointment",
                "args": {"date": date, "time": time, "phone_number": normalized_phone, "name": name},
                "result": result,
            },
        )
        return result

    result = f"Your appointment is booked for {date} at {time}."
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "book_appointment",
            "args": {"date": date, "time": time, "phone_number": normalized_phone, "name": name},
            "result": result,
        },
    )
    return result


@function_tool
async def retrieve_appointments(
    context: RunContext,
    phone_number: Optional[str] = None,
):
    """Retrieve past appointments for a user. If phone_number is not provided, it will ask for it."""
    logger.info(f"retrieve_appointments called with phone_number={phone_number}")
    normalized_phone = _normalize_phone_number(phone_number) or phone_number
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "retrieve_appointments",
            "args": {"phone_number": normalized_phone},
        },
    )
    if not phone_number:
        result = "I need your phone number to look up your appointments. Could you please provide it?"
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "retrieve_appointments",
                "args": {"phone_number": normalized_phone},
                "result": result,
            },
        )
        return result

    supabase = await get_supabase()
    try:
        res = (
            await supabase.table("appointments")
            .select("*")
            .eq("contact_number", normalized_phone)
            .execute()
        )

        if not res.data:
            result = f"I couldn't find any appointments for the phone number {normalized_phone}."
            await _publish_tool_event(
                context,
                {
                    "type": "tool_call",
                    "name": "retrieve_appointments",
                    "args": {"phone_number": normalized_phone},
                    "result": result,
                },
            )
            return result

        logger.info(f"Retrieved {len(res.data)} appointments.")
        summaries = []
        internal_ids = []
        for idx, appt in enumerate(res.data, start=1):
            date = appt.get("date")
            time = appt.get("time")
            status = appt.get("status", "unknown")
            summaries.append(f"{idx}. {date} at {time} ({status})")
            internal_ids.append(f"{idx}|{appt.get('id')}")

        spoken_summary = (
            "Here are your appointments: " + "; ".join(summaries) + "."
        )
        internal_block = (
            "DO_NOT_READ_INTERNAL_IDS:\n" + "\n".join(internal_ids)
        )
        result = spoken_summary + "\n" + internal_block

        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "retrieve_appointments",
                "args": {"phone_number": normalized_phone},
                "result": res.data,
            },
        )
        return result
    except Exception as e:
        logger.error(f"Error retrieving appointments: {e}", exc_info=True)
        result = "I'm sorry, I encountered an error while looking up your appointments."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "retrieve_appointments",
                "args": {"phone_number": normalized_phone},
                "result": result,
            },
        )
        return result


@function_tool
async def cancel_appointment(
    context: RunContext,
    appointment_id: str,
):
    """Cancel an appointment."""
    await _publish_tool_event(
        context,
        {"type": "tool_call", "name": "cancel_appointment", "args": {"appointment_id": appointment_id}},
    )
    supabase = await get_supabase()
    appt_res = (
        await supabase.table("appointments")
        .select("date,time,status")
        .eq("id", appointment_id)
        .execute()
    )

    if not appt_res.data:
        result = "I couldn't find that appointment. Please check the appointment ID."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "cancel_appointment",
                "args": {"appointment_id": appointment_id},
                "result": result,
            },
        )
        return result

    appointment = appt_res.data[0]
    date = appointment.get("date")
    time = appointment.get("time")

    await supabase.table("appointments") \
        .update({"status": "cancelled"}) \
        .eq("id", appointment_id) \
        .execute()

    if date and time:
        await supabase.table("slots") \
            .update({"is_booked": False}) \
            .eq("date", date) \
            .eq("time", time) \
            .execute()

    result = "Your appointment has been cancelled and the slot is now available."
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "cancel_appointment",
            "args": {"appointment_id": appointment_id},
            "result": result,
        },
    )
    return result


@function_tool
async def modify_appointment(
    context: RunContext,
    appointment_id: str,
    new_date: str,
    new_time: str,
):
    """Modify appointment date or time."""
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "modify_appointment",
            "args": {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time},
        },
    )
    supabase = await get_supabase()

    if new_date and len(new_date) == 10 and new_date[2] == "-" and new_date[5] == "-":
        parts = new_date.split("-")
        if len(parts) == 3:
            new_date = f"{parts[2]}-{parts[1]}-{parts[0]}"

    appt_res = (
        await supabase.table("appointments")
        .select("id,date,time,status")
        .eq("id", appointment_id)
        .execute()
    )

    if not appt_res.data:
        result = "I couldn't find that appointment."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "modify_appointment",
                "args": {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time},
                "result": result,
            },
        )
        return result

    current = appt_res.data[0]
    old_date = current.get("date")
    old_time = current.get("time")

    slot_check = (
        await supabase.table("slots")
        .select("*")
        .eq("date", new_date)
        .eq("time", new_time)
        .eq("is_booked", False)
        .execute()
    )

    if not slot_check.data:
        result = "That new slot is not available. Please choose another time."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "modify_appointment",
                "args": {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time},
                "result": result,
            },
        )
        return result

    conflict = (
        await supabase.table("appointments")
        .select("*")
        .eq("date", new_date)
        .eq("time", new_time)
        .eq("status", "booked")
        .execute()
    )

    if conflict.data:
        result = "That new slot is already booked."
        await _publish_tool_event(
            context,
            {
                "type": "tool_call",
                "name": "modify_appointment",
                "args": {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time},
                "result": result,
            },
        )
        return result

    await supabase.table("appointments") \
        .update({"date": new_date, "time": new_time, "status": "booked"}) \
        .eq("id", appointment_id) \
        .execute()

    if old_date and old_time:
        await supabase.table("slots") \
            .update({"is_booked": False}) \
            .eq("date", old_date) \
            .eq("time", old_time) \
            .execute()

    await supabase.table("slots") \
        .update({"is_booked": True}) \
        .eq("date", new_date) \
        .eq("time", new_time) \
        .execute()

    result = f"Your appointment has been moved to {new_date} at {new_time}."
    await _publish_tool_event(
        context,
        {
            "type": "tool_call",
            "name": "modify_appointment",
            "args": {"appointment_id": appointment_id, "new_date": new_date, "new_time": new_time},
            "result": result,
        },
    )
    return result
