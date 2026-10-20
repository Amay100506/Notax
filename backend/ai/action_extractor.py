"""
Action Extractor for NotifyIQ.
Detects potential tasks, calls-to-action, and requests within notification text.
Uses contextual grammar and keyword rules to avoid false positives.
"""

import re
from typing import Optional
from pydantic import BaseModel


class ActionExtractionResult(BaseModel):
    action_detected: bool = False
    action_type: Optional[str] = None
    action_text: Optional[str] = None
    evidence: Optional[str] = None
    action_certainty: float = 0.0  # 0.0 to 1.0


# Configurable action verbs vocabulary
ACTION_VERBS = [
    "submit",
    "complete",
    "review",
    "approve",
    "confirm",
    "verify",
    "respond",
    "reply",
    "pay",
    "upload",
    "register",
    "attend",
    "renew",
    "collect",
    "sign",
    "schedule",
    "book",
    "update",
    "fill",
    "download",
    "recharge",
    "bharo",
    "bharein",
]

# Patterns signaling explicit directives (English & Hinglish)
IMPERATIVE_PREFIXES = [
    r"please\s+",
    r"kindly\s+",
    r"kripya\s+",
    r"action\s+needed:?\s*",
    r"action\s+required:?\s*",
    r"urgent:?\s*",
    r"reminder:?\s*",
    r"you\s+need\s+to\s+",
    r"you\s+must\s+",
    r"requires\s+your\s+",
    r"don't\s+forget\s+to\s+",
    r"tap\s+to\s+",
    r"turant\s+",
    r"jaldi\s+",
    r"aaj\s+hi\s+",
    r"dhyaan\s+dein:?\s*",
]


def extract_action(text: str, title: str = "") -> ActionExtractionResult:
    """
    Analyzes notification text and title to detect actionable directives.
    Returns structured ActionExtractionResult.
    """
    combined = f"{title}. {text}".strip().lower()
    if not combined or combined == ".":
        return ActionExtractionResult()

    # Check for imperative cues
    has_imperative_cue = any(re.search(pat, combined) for pat in IMPERATIVE_PREFIXES)

    best_verb: Optional[str] = None
    best_match_phrase: Optional[str] = None
    highest_certainty = 0.0

    # Test each action verb
    for verb in ACTION_VERBS:
        # Match verb followed by object / preposition (e.g., "submit your assignment", "review pull request")
        pattern = rf"\b(?:please\s+|kindly\s+|kripya\s+|to\s+)?({verb})\b\s+([a-zA-Z0-9_\-#\s]{{3,40}})"
        match = re.search(pattern, combined)
        # Also check object + verb order (SOV grammar common in Hinglish, e.g., "form bharein")
        if not match:
            sov_pattern = rf"\b([a-zA-Z0-9_\-#\s]{{2,30}})\s+({verb})\b"
            match = re.search(sov_pattern, combined)

        if match:
            verb_matched = verb
            phrase = match.group(0).strip().capitalize()
            certainty = 0.85 if has_imperative_cue else 0.65

            # Boost if verb is at the start of sentence
            if re.search(rf"(?:^|[.!?]\s*)({verb})\b", combined):
                certainty = min(1.0, certainty + 0.15)

            if certainty > highest_certainty:
                highest_certainty = certainty
                best_verb = verb_matched
                best_match_phrase = phrase

    # Check for deadline-associated action keywords (e.g., "due tomorrow", "expires soon")
    if not best_verb:
        due_match = re.search(r"\b(due|expires|deadline)\b\s*(?:is|on|by|in)?\s*([a-zA-Z0-9_\-#\s]{3,30})", combined)
        if due_match:
            best_verb = "complete"
            best_match_phrase = due_match.group(0).strip().capitalize()
            highest_certainty = 0.70

    if best_verb and highest_certainty >= 0.50:
        return ActionExtractionResult(
            action_detected=True,
            action_type=best_verb,
            action_text=best_match_phrase or f"{best_verb.capitalize()} requested item",
            evidence=best_match_phrase,
            action_certainty=round(highest_certainty, 2),
        )

    return ActionExtractionResult(action_detected=False)
