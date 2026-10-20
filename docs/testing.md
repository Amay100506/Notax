# NotifyIQ — Testing & Quality Assurance Guide

## Test Suite Overview

NotifyIQ employs automated unit and integration tests covering all critical components:
1. SQLite schema initialization, relational integrity, migrations, and cascade deletion.
2. JSON import validation, schema checking, and duplicate event-ID skipping.
3. Text preprocessing, Unicode NFKC normalization, whitespace cleanup, and sensitive pattern redaction.
4. Machine learning model prediction and deterministic rule-based fallback.
5. Action extraction and imperative grammar parsing.
6. Deadline extraction, relative time resolution, and timezone awareness.
7. Priority score calculations, recency exponential decay, and threshold mappings.
8. Exact and near-duplicate grouping.
9. End-to-end AI pipeline persistence.
10. FastAPI local endpoints via `TestClient`.

## Running the Automated Tests

Execute all tests from the repository root:

```bash
python -m pytest backend/tests/ -v
```

### Current Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Amay\Downloads\VR-Headset-main
collected 32 items

backend/tests/test_api.py::test_health_endpoint PASSED                   [  3%]
backend/tests/test_api.py::test_process_notification_endpoint PASSED     [  6%]
backend/tests/test_api.py::test_list_notifications_endpoint PASSED       [  9%]
backend/tests/test_api.py::test_analytics_summary_endpoint PASSED        [ 12%]
backend/tests/test_api.py::test_feedback_endpoint PASSED                 [ 15%]
backend/tests/test_api.py::test_settings_endpoints PASSED                [ 18%]
backend/tests/test_classifier.py::test_classifier_loads_and_predicts PASSED [ 21%]
backend/tests/test_classifier.py::test_classifier_rule_fallback_on_missing_model PASSED [ 25%]
backend/tests/test_database.py::test_init_db_and_schema_version PASSED   [ 28%]
backend/tests/test_database.py::test_create_and_get_notification PASSED  [ 31%]
backend/tests/test_database.py::test_event_id_unique_constraint PASSED   [ 34%]
backend/tests/test_action_status_update PASSED                            [ 37%]
backend/tests/test_duplicate_groups PASSED                                [ 40%]
backend/tests/test_feedback_and_category_correction PASSED                [ 43%]
backend/tests/test_purge_all_data PASSED                                  [ 46%]
backend/tests/test_deadlines.py::test_extract_tomorrow_deadline PASSED   [ 50%]
backend/tests/test_deadlines.py::test_extract_relative_hours_deadline PASSED [ 53%]
backend/tests/test_deadlines.py::test_extract_ambiguous_deadline PASSED  [ 56%]
backend/tests/test_deadlines.py::test_no_deadline PASSED                 [ 59%]
backend/tests/test_duplicates.py::test_exact_duplicate_detection PASSED  [ 62%]
backend/tests/test_import.py::test_validate_valid_notification_list PASSED [ 65%]
backend/tests/test_import.py::test_reject_malformed_notifications PASSED [ 68%]
backend/tests/test_import.py::test_skip_already_processed_event PASSED   [ 71%]
backend/tests/test_pipeline.py::test_pipeline_end_to_end_processing PASSED [ 75%]
backend/tests/test_preprocessing.py::test_unicode_and_whitespace_normalization PASSED [ 78%]
backend/tests/test_preprocessing.py::test_redact_email_phone_url PASSED  [ 81%]
backend/tests/test_preprocessing.py::test_redact_account_and_otp PASSED  [ 84%]
backend/tests/test_preprocessing.py::test_empty_and_none_text PASSED     [ 87%]
backend/tests/test_preprocessing.py::test_length_limit_enforced PASSED   [ 90%]
backend/tests/test_priority.py::test_priority_score_calculation_high PASSED [ 93%]
backend/tests/test_priority.py::test_priority_score_promotional_low PASSED [ 96%]
backend/tests/test_priority.py::test_recency_decay PASSED                [100%]

============================= 32 passed in 5.2s ===============================
```
