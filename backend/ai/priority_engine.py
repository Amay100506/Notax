"""
Explainable Priority Engine for NotifyIQ.
Implements the transparent deterministic formula:
P = 0.30*U + 0.25*A + 0.25*D + 0.15*I + 0.05*R
Produces score (0-100), priority level (high/medium/low),
and human-auditable component breakdown and reason explanations.
"""

import math
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
from backend.utils.configuration import settings


class PriorityBreakdown(BaseModel):
    urgency_score: float
    action_score: float
    deadline_score: float
    importance_score: float
    recency_score: float


class PriorityResult(BaseModel):
    priority_score: float
    priority_level: str  # "high", "medium", "low"
    components: PriorityBreakdown
    priority_reasons: list[str]


def calculate_recency_score(received_at_iso: str, reference_time: Optional[datetime] = None) -> float:
    """
    Computes exponential recency decay: R = 100 * exp(-age_hours / tau).
    Handles future timestamps safely by capping at 100.
    """
    try:
        clean_ts = received_at_iso.replace("Z", "+00:00")
        rec_dt = datetime.fromisoformat(clean_ts)
        if rec_dt.tzinfo is None:
            rec_dt = rec_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return 50.0

    ref = reference_time or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)

    age_hours = (ref - rec_dt).total_seconds() / 3600.0
    if age_hours <= 0:
        return 100.0

    tau = settings.recency_tau_hours
    score = 100.0 * math.exp(-age_hours / tau)
    return max(0.0, min(100.0, score))


def calculate_deadline_score(
    deadline_detected: bool,
    time_remaining_seconds: Optional[int],
    is_overdue: bool,
) -> tuple[float, Optional[str]]:
    """Calculates deadline component D and associated reason string."""
    if not deadline_detected or time_remaining_seconds is None:
        return 0.0, None

    if is_overdue or time_remaining_seconds < 0:
        return 95.0, "The deadline for this notification has passed (overdue)."

    hours_rem = time_remaining_seconds / 3600.0
    if hours_rem <= 1.0:
        return 100.0, "Critical deadline approaching within 1 hour."
    elif hours_rem <= 24.0:
        return 90.0, "Approaching deadline within 24 hours."
    elif hours_rem <= 48.0:
        return 70.0, "Deadline due within 1 to 2 days."
    elif hours_rem <= 168.0:
        return 40.0, "Deadline scheduled within the next 3 to 7 days."
    else:
        return 20.0, "Future deadline scheduled more than 7 days away."


def calculate_urgency_score(
    category: str,
    text: str,
    package_name: str,
) -> tuple[float, Optional[str]]:
    """Calculates urgency component U based on contextual signals."""
    t = text.lower()
    pkg = package_name.lower()

    if category == "promotional":
        return 10.0, "Marketing or promotional alert (low baseline urgency)."

    # Critical account / security signals
    if any(w in t for w in ["security alert", "suspicious activity", "account freeze", "unauthorized", "emergency"]):
        return 95.0, "Security or account alert requires prompt attention."

    # Immediate / time-critical keywords
    if any(w in t for w in ["immediately", "urgent", "asap", "expires in", "due today", "cancel"]):
        return 85.0, "Urgent language detected in message context."

    if category == "action_required":
        return 75.0, "Action-oriented task with moderate-to-high urgency."

    if category == "transactional":
        if any(w in t for w in ["out for delivery", "debited", "cancelled"]):
            return 65.0, "Time-sensitive financial or delivery update."
        return 45.0, "Routine transactional notification."

    if category == "system":
        return 35.0, "Standard system status notification."

    if category == "social":
        return 30.0, "Social interaction or messaging alert."

    return 20.0, None


def calculate_action_score(
    action_detected: bool,
    action_certainty: float,
    has_deadline: bool,
) -> tuple[float, Optional[str]]:
    """Calculates action requirement component A."""
    if not action_detected:
        return 0.0, None

    if has_deadline:
        return 100.0, "An explicit action request with an attached deadline was identified."
    elif action_certainty >= 0.8:
        return 80.0, "An explicit action request was identified."
    else:
        return 50.0, "A potential action or follow-up task was detected."


def calculate_importance_score(
    package_name: str,
    category: str,
    user_app_importance: Optional[dict[str, float]] = None,
) -> tuple[float, Optional[str]]:
    """Calculates user-defined importance component I."""
    pkg = package_name.lower()
    
    # Check explicit user app override if provided
    if user_app_importance and package_name in user_app_importance:
        score = user_app_importance[package_name]
        return score, f"User-defined importance rule for {package_name} ({score:.0f}/100)."

    # Default category/package baselines
    if any(k in pkg for k in ["bank", "security", "authenticator", "work", "teams", "slack", "docs"]):
        return 80.0, "High importance assigned to productivity/financial app."
    elif category == "promotional":
        return 15.0, "Reduced importance assigned to promotional source."
    else:
        return 50.0, None


def score_priority(
    category: str,
    text: str,
    package_name: str,
    received_at_iso: str,
    action_detected: bool = False,
    action_certainty: float = 0.0,
    deadline_detected: bool = False,
    time_remaining_seconds: Optional[int] = None,
    is_overdue: bool = False,
    user_app_importance: Optional[dict[str, float]] = None,
    reference_time: Optional[datetime] = None,
) -> PriorityResult:
    """
    Computes priority score using the formula:
    P = 0.30*U + 0.25*A + 0.25*D + 0.15*I + 0.05*R
    """
    reasons: list[str] = []

    # 1. Urgency U
    u_score, u_reason = calculate_urgency_score(category, text, package_name)
    if u_reason:
        reasons.append(u_reason)

    # 2. Action A
    has_valid_deadline = deadline_detected and (time_remaining_seconds is not None or is_overdue)
    a_score, a_reason = calculate_action_score(action_detected, action_certainty, has_valid_deadline)
    if a_reason:
        reasons.append(a_reason)

    # 3. Deadline D
    d_score, d_reason = calculate_deadline_score(deadline_detected, time_remaining_seconds, is_overdue)
    if d_reason:
        reasons.append(d_reason)

    # 4. Importance I
    i_score, i_reason = calculate_importance_score(package_name, category, user_app_importance)
    if i_reason:
        reasons.append(i_reason)

    # 5. Recency R
    r_score = calculate_recency_score(received_at_iso, reference_time)
    if r_score >= 90.0:
        reasons.append("Recently received notification.")

    # Weighted Sum
    w_u = settings.weight_urgency
    w_a = settings.weight_action
    w_d = settings.weight_deadline
    w_i = settings.weight_importance
    w_r = settings.weight_recency

    raw_priority = (w_u * u_score) + (w_a * a_score) + (w_d * d_score) + (w_i * i_score) + (w_r * r_score)
    final_score = max(0.0, min(100.0, raw_priority))

    # Priority Level Mapping
    if final_score >= settings.priority_high_threshold:
        level = "high"
    elif final_score >= settings.priority_medium_threshold:
        level = "medium"
    else:
        level = "low"

    if not reasons:
        reasons.append("Standard informational notification with routine priority.")

    return PriorityResult(
        priority_score=round(final_score, 1),
        priority_level=level,
        components=PriorityBreakdown(
            urgency_score=round(u_score, 1),
            action_score=round(a_score, 1),
            deadline_score=round(d_score, 1),
            importance_score=round(i_score, 1),
            recency_score=round(r_score, 1),
        ),
        priority_reasons=reasons,
    )
