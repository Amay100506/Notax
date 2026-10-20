"""
Calendar sync utilities for NotifyIQ.
Generates standard RFC 5545 iCalendar (.ics) files and direct one-click
URLs for Google Calendar and Outlook Web Calendar.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import urllib.parse


def format_ics_datetime(dt: datetime) -> str:
    """Formats a datetime into iCalendar UTC format (YYYYMMDDTHHMMSSZ)."""
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y%m%dT%H%M%SZ")


def generate_google_calendar_url(
    title: str,
    description: str,
    deadline_at: datetime,
    duration_minutes: int = 30,
) -> str:
    """
    Generates a one-click Google Calendar web creation URL.
    Opens directly in browser with title, date/time, and context pre-filled.
    """
    start_time = deadline_at
    end_time = deadline_at + timedelta(minutes=duration_minutes)

    start_str = format_ics_datetime(start_time)
    end_str = format_ics_datetime(end_time)

    params = {
        "action": "TEMPLATE",
        "text": title.strip(),
        "dates": f"{start_str}/{end_str}",
        "details": f"{description}\n\n[Tracked automatically by NotifyIQ AI]",
        "sf": "true",
        "output": "xml",
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)


def generate_outlook_calendar_url(
    title: str,
    description: str,
    deadline_at: datetime,
    duration_minutes: int = 30,
) -> str:
    """Generates a one-click Outlook Web Calendar event URL."""
    start_time = deadline_at
    end_time = deadline_at + timedelta(minutes=duration_minutes)

    start_iso = start_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": title.strip(),
        "startdt": start_iso,
        "enddt": end_iso,
        "body": f"{description}\n\n[Tracked automatically by NotifyIQ AI]",
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urllib.parse.urlencode(params)


def generate_ics_content(
    title: str,
    description: str,
    deadline_at: datetime,
    event_uid: Optional[str] = None,
    duration_minutes: int = 30,
) -> str:
    """
    Generates an RFC 5545 compliant iCalendar (.ics) string.
    Compatible with Apple Calendar, Google Calendar, Outlook, and Android.
    """
    now_str = format_ics_datetime(datetime.now(timezone.utc))
    start_str = format_ics_datetime(deadline_at)
    end_str = format_ics_datetime(deadline_at + timedelta(minutes=duration_minutes))
    uid = event_uid or f"notifyiq-{int(deadline_at.timestamp())}@notifyiq.local"

    # Clean multi-line strings for RFC 5545
    clean_title = title.replace("\n", " ").replace(";", "\\;").replace(",", "\\,")
    clean_desc = (
        description.replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NotifyIQ//Smart Notification Intelligence//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_str}",
        f"DTSTART:{start_str}",
        f"DTEND:{end_str}",
        f"SUMMARY:{clean_title}",
        f"DESCRIPTION:{clean_desc}\\n\\n[Tracked by NotifyIQ]",
        "STATUS:CONFIRMED",
        "BEGIN:VALARM",
        "TRIGGER:-PT15M",
        "ACTION:DISPLAY",
        "DESCRIPTION:Reminder: " + clean_title,
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(ics_lines) + "\r\n"
