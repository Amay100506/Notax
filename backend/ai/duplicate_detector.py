"""
Duplicate Detection Engine for NotifyIQ.
Implements two-level grouping:
Level 1: Deterministic exact duplicate fingerprinting.
Level 2: Conservative near-duplicate similarity (TF-IDF cosine similarity).
Preserves all source notification records.
"""

import hashlib
import re
from typing import Optional
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.database.repository import Repository
from backend.utils.configuration import settings


class DuplicateCheckResult(BaseModel):
    is_duplicate: bool = False
    duplicate_group_id: Optional[str] = None
    grouping_method: str = "none"  # "exact", "near_duplicate", "none"
    similarity_score: Optional[float] = None
    group_fingerprint: Optional[str] = None


class DuplicateDetector:
    def __init__(self, repository: Optional[Repository] = None):
        self.repository = repository or Repository()
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)

    def generate_exact_fingerprint(self, package_name: str, title: str, text: str) -> str:
        """Generates a normalized 16-character SHA-256 fingerprint for exact matching."""
        norm_pkg = package_name.strip().lower()
        norm_title = re.sub(r"\s+", " ", title.strip().lower())
        norm_text = re.sub(r"\s+", " ", text.strip().lower())
        combined = f"{norm_pkg}::{norm_title}::{norm_text}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

    def check_duplicate(
        self,
        package_name: str,
        title: str,
        text: str,
        enable_near_duplicates: bool = True,
    ) -> DuplicateCheckResult:
        """
        Evaluates incoming notification against previously ingested notifications.
        Returns DuplicateCheckResult with group assignment.
        """
        # Step 1: Level 1 - Exact Duplicate Check
        exact_fp = self.generate_exact_fingerprint(package_name, title, text)
        exact_group = self.repository.get_or_create_group(fingerprint=exact_fp, method="exact")
        
        # Check how many existing members are in this group
        members = self.repository.get_group_members(exact_group["id"])
        if members:
            # Already has prior members -> This incoming event is an exact duplicate!
            return DuplicateCheckResult(
                is_duplicate=True,
                duplicate_group_id=exact_group["id"],
                grouping_method="exact",
                similarity_score=1.0,
                group_fingerprint=exact_fp,
            )

        # Step 2: Level 2 - Near Duplicate Similarity Check (optional & conservative)
        if enable_near_duplicates and text.strip():
            recent_notifs, _ = self.repository.list_notifications(
                package_name=package_name,
                limit=30,
            )
            incoming_combined = f"{title} {text}".strip()

            best_sim = 0.0
            best_match_id = None
            best_group_id = None

            for past in recent_notifs:
                past_combined = f"{past.get('title', '')} {past.get('text', '')}".strip()
                if not past_combined:
                    continue

                try:
                    tfidf = self._vectorizer.fit_transform([incoming_combined, past_combined])
                    sim = float(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
                    if sim > best_sim:
                        best_sim = sim
                        best_match_id = past["id"]
                        best_group_id = past.get("duplicate_group_id")
                except Exception:
                    continue

            # Compare against conservative threshold (default 0.85)
            if best_sim >= settings.near_dup_threshold and best_match_id:
                near_fp = f"near-{best_match_id[:8]}"
                near_group = self.repository.get_or_create_group(
                    fingerprint=near_fp,
                    method="near_duplicate",
                    threshold=settings.near_dup_threshold,
                )
                return DuplicateCheckResult(
                    is_duplicate=True,
                    duplicate_group_id=near_group["id"],
                    grouping_method="near_duplicate",
                    similarity_score=round(best_sim, 2),
                    group_fingerprint=near_fp,
                )

        # If not a duplicate, return the exact group ID as its primary group anchor
        return DuplicateCheckResult(
            is_duplicate=False,
            duplicate_group_id=exact_group["id"],
            grouping_method="exact_anchor",
            similarity_score=1.0,
            group_fingerprint=exact_fp,
        )
