"""
Deadline and Time Expression Extractor for NotifyIQ.
Extracts relative and absolute time expressions using the notification timestamp as reference.
Resolves timestamps with explicit timezone support and flags ambiguous expressions.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from backend.utils.configuration import settings


class DeadlineExtractionResult(BaseModel):
    deadline_detected: bool = False
    deadline_text: Optional[str] = None
    deadline_at: Optional[str] = None
    resolution_status: str = "none"  # "resolved", "unresolved", "none"
    time_remaining_seconds: Optional[int] = None
    is_overdue: bool = False


# Weekday mapping
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6
}

# Month mapping
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}


def parse_reference_time(ref_time_str: Optional[str]) -> datetime:
    """Parses reference time string, ensuring timezone awareness."""
    tz = ZoneInfo(settings.timezone)
    if not ref_time_str:
        return datetime.now(tz)
    try:
        clean_str = ref_time_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(tz)
    except Exception:
        return datetime.now(tz)


def extract_time_part(text: str) -> Optional[tuple[int, int]]:
    """Extracts hour and minute from strings like '5 PM', '6:30 PM', '11:59 PM', 'noon', 'midnight'."""
    text_lower = text.lower()
    if "midnight" in text_lower or "raat" in text_lower:
        return 23, 59
    if "noon" in text_lower or "dopahar" in text_lower:
        return 12, 0
    if "shaam" in text_lower or "sham" in text_lower:
        return 18, 0
    if "subah" in text_lower:
        return 9, 0

    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text_lower)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2)) if time_match.group(2) else 0
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        return hour, minute

    return None


def extract_deadline(
    text: str,
    title: str = "",
    reference_time_str: Optional[str] = None,
) -> DeadlineExtractionResult:
    """
    Scans notification title and text for deadline expressions and resolves them
    relative to reference_time_str.
    """
    combined = f"{title} {text}".strip()
    if not combined:
        return DeadlineExtractionResult()

    ref_dt = parse_reference_time(reference_time_str)
    combined_lower = combined.lower()

    # 1. Check relative hour/minute offsets: "in 2 hours", "in 30 minutes", "within 24 hours"
    offset_match = re.search(r"\b(?:in|within)\s+(\d{1,3})\s+(hour|hr|minute|min|day)s?\b", combined_lower)
    if offset_match:
        amount = int(offset_match.group(1))
        unit = offset_match.group(2)
        phrase = offset_match.group(0)

        if "day" in unit:
            resolved_dt = ref_dt + timedelta(days=amount)
        elif "hour" in unit or "hr" in unit:
            resolved_dt = ref_dt + timedelta(hours=amount)
        else:
            resolved_dt = ref_dt + timedelta(minutes=amount)

        rem_secs = int((resolved_dt - ref_dt).total_seconds())
        return DeadlineExtractionResult(
            deadline_detected=True,
            deadline_text=phrase,
            deadline_at=resolved_dt.isoformat(),
            resolution_status="resolved",
            time_remaining_seconds=rem_secs,
            is_overdue=rem_secs < 0,
        )

    # 2. Check "today" or "tonight"
    today_match = re.search(r"\b(?:by|before|at)?\s*(today|tonight)(?:\s+(?:at|by)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?\b", combined_lower)
    if today_match:
        phrase = today_match.group(0).strip()
        time_part = extract_time_part(combined_lower)
        if time_part:
            hour, minute = time_part
        elif "tonight" in phrase:
            hour, minute = 21, 0
        else:
            hour, minute = 18, 0

        resolved_dt = ref_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        rem_secs = int((resolved_dt - ref_dt).total_seconds())
        return DeadlineExtractionResult(
            deadline_detected=True,
            deadline_text=phrase,
            deadline_at=resolved_dt.isoformat(),
            resolution_status="resolved",
            time_remaining_seconds=rem_secs,
            is_overdue=rem_secs < 0,
        )

    # 3. Check "tomorrow" or "kal"
    tomorrow_match = re.search(
        r"\b(?:by|before|at|due|expires)?\s*(?:tomorrow|kal)(?:\s+(?:at|by|noon|midnight|sham|shaam|subah)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?\b",
        combined_lower,
    )
    if tomorrow_match:
        phrase = tomorrow_match.group(0).strip()
        time_part = extract_time_part(combined_lower)
        hour, minute = time_part if time_part else (18, 0)

        tomorrow_dt = ref_dt + timedelta(days=1)
        resolved_dt = tomorrow_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        rem_secs = int((resolved_dt - ref_dt).total_seconds())
        return DeadlineExtractionResult(
            deadline_detected=True,
            deadline_text=phrase,
            deadline_at=resolved_dt.isoformat(),
            resolution_status="resolved",
            time_remaining_seconds=rem_secs,
            is_overdue=rem_secs < 0,
        )

    # 4. Check "today" or "aaj"
    today_match = re.search(
        r"\b(?:by|before|at|due|expires)?\s*(?:today|tonight|aaj)(?:\s+(?:at|by|noon|midnight|sham|shaam|subah)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?\b",
        combined_lower,
    )
    if today_match:
        phrase = today_match.group(0).strip()
        time_part = extract_time_part(combined_lower)
        hour, minute = time_part if time_part else (20, 0)

        resolved_dt = ref_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        rem_secs = int((resolved_dt - ref_dt).total_seconds())
        return DeadlineExtractionResult(
            deadline_detected=True,
            deadline_text=phrase,
            deadline_at=resolved_dt.isoformat(),
            resolution_status="resolved",
            time_remaining_seconds=rem_secs,
            is_overdue=rem_secs < 0,
        )

    # 4. Check "by/before [Time]" without specific date (assumed today or next occurrence)
    by_time_match = re.search(r"\b(?:by|before|due at)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)|noon|midnight)\b", combined_lower)
    if by_time_match:
        phrase = by_time_match.group(0).strip()
        time_part = extract_time_part(phrase)
        if time_part:
            hour, minute = time_part
            resolved_dt = ref_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if resolved_dt < ref_dt:
                # If time already passed today, likely today past deadline or tomorrow
                pass
            rem_secs = int((resolved_dt - ref_dt).total_seconds())
            return DeadlineExtractionResult(
                deadline_detected=True,
                deadline_text=phrase,
                deadline_at=resolved_dt.isoformat(),
                resolution_status="resolved",
                time_remaining_seconds=rem_secs,
                is_overdue=rem_secs < 0,
            )

    # 5. Check weekdays: "by Friday", "before Monday 5 PM"
    weekday_pat = r"\b(?:by|before|on|due)\s+(" + "|".join(WEEKDAYS.keys()) + r")(?:\s+(?:at|by)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?\b"
    weekday_match = re.search(weekday_pat, combined_lower)
    if weekday_match:
        day_name = weekday_match.group(1)
        phrase = weekday_match.group(0).strip()
        target_wd = WEEKDAYS[day_name]
        current_wd = ref_dt.weekday()

        days_ahead = (target_wd - current_wd) % 7
        if days_ahead == 0:
            days_ahead = 7  # Next week's occurrence

        time_part = extract_time_part(combined_lower)
        hour, minute = time_part if time_part else (18, 0)
        resolved_dt = (ref_dt + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        rem_secs = int((resolved_dt - ref_dt).total_seconds())
        return DeadlineExtractionResult(
            deadline_detected=True,
            deadline_text=phrase,
            deadline_at=resolved_dt.isoformat(),
            resolution_status="resolved",
            time_remaining_seconds=rem_secs,
            is_overdue=rem_secs < 0,
        )

    # 6. Check explicit calendar dates: "October 25", "due on 25 October"
    month_names = "|".join(MONTHS.keys())
    date_pat1 = rf"\b(?:by|before|due on|on)?\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_names})(?:\s+(\d{{4}}))?(?:\s+(?:at|by)?\s*(\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?))?\b"
    date_pat2 = rf"\b(?:by|before|due on|on)?\s*({month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+(\d{{4}}))?(?:\s+(?:at|by)?\s*(\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?))?\b"

    d1 = re.search(date_pat1, combined_lower)
    d2 = re.search(date_pat2, combined_lower)
    if d1 or d2:
        m = d1 if d1 else d2
        phrase = m.group(0).strip()
        if d1:
            day = int(d1.group(1))
            month = MONTHS[d1.group(2)]
            year = int(d1.group(3)) if d1.group(3) else ref_dt.year
        else:
            month = MONTHS[d2.group(1)]
            day = int(d2.group(2))
            year = int(d2.group(3)) if d2.group(3) else ref_dt.year

        time_part = extract_time_part(combined_lower)
        hour, minute = time_part if time_part else (23, 59)

        try:
            resolved_dt = ref_dt.replace(year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            rem_secs = int((resolved_dt - ref_dt).total_seconds())
            return DeadlineExtractionResult(
                deadline_detected=True,
                deadline_text=phrase,
                deadline_at=resolved_dt.isoformat(),
                resolution_status="resolved",
                time_remaining_seconds=rem_secs,
                is_overdue=rem_secs < 0,
            )
        except ValueError:
            pass

    # 7. Check ambiguous expressions: "by next week", "sometime soon", "in a few days"
    ambiguous_match = re.search(r"\b(by next week|sometime soon|in a few days|due shortly|expires soon)\b", combined_lower)
    if ambiguous_match:
        return DeadlineExtractionResult(
            deadline_detected=True,
            deadline_text=ambiguous_match.group(0),
            deadline_at=None,
            resolution_status="unresolved",
            time_remaining_seconds=None,
            is_overdue=False,
        )

    # 8. Open-Source Dateparser NLP Integration (for natural language deadlines)
    try:
        import dateparser
        cue_match = re.search(
            r"\b(?:due|before|expires|until|valid till|valid until|closes on|deadline is)\s+([A-Za-z0-9\s,:\-]+?)(?:\.|\n|$|!|\?)",
            combined,
            re.IGNORECASE,
        )
        if cue_match:
            candidate_phrase = cue_match.group(1).strip()
            # Avoid single generic words
            if len(candidate_phrase.split()) >= 1 and not re.match(r"^(?:soon|shortly|now)$", candidate_phrase, re.IGNORECASE):
                parsed_dt = dateparser.parse(
                    candidate_phrase,
                    settings={
                        "RELATIVE_BASE": ref_dt.replace(tzinfo=None),
                        "PREFER_DATES_FROM": "future",
                        "RETURN_AS_TIMEZONE_AWARE": False,
                    },
                )
                if parsed_dt:
                    tz = ZoneInfo(settings.timezone)
                    resolved_dt = parsed_dt.replace(tzinfo=tz)
                    rem_secs = int((resolved_dt - ref_dt).total_seconds())
                    return DeadlineExtractionResult(
                        deadline_detected=True,
                        deadline_text=cue_match.group(0).strip(),
                        deadline_at=resolved_dt.isoformat(),
                        resolution_status="resolved",
                        time_remaining_seconds=rem_secs,
                        is_overdue=rem_secs < 0,
                    )
    except Exception:
        pass

    return DeadlineExtractionResult(deadline_detected=False, resolution_status="none")
