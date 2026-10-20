# NotifyIQ — Competition Demonstration Guide

**Target Presentation Time**: 3 to 5 minutes  
**Target Audience**: Competition Judges, Technical Evaluators, Privacy Advocates

---

## 1. Introduction: The Notification Overload Dilemma (0:00 – 0:45)

- **The Problem**: Modern mobile users receive 60–100+ notifications daily. Critical assignment deadlines, time-sensitive security alerts, and important communications are routinely buried under flash sales, marketing promotions, and routine social chatter.
- **The Pitfall of Existing Tools**: Traditional systems offer coarse app-level muting or push notification bodies to cloud LLM APIs, exposing sensitive bank balances, private messages, and verification codes.
- **NotifyIQ Solution**: A privacy-first, explainable AI system running 100% locally. It answers:
  1. *What type of notification is this?*
  2. *How important is it?*
  3. *Does it require an action?*
  4. *Does it contain a deadline?*
  5. *Why did the AI assign this priority?*

---

## 2. Privacy-First Capture Architecture (0:45 – 1:30)

- **Android Companion App**:
  - Show the Kotlin companion interface.
  - Explain the explicit Android `NotificationListenerService` consent flow.
  - Highlight the App Allowlist and instant Pause toggle.
  - Show the JSON Export button: no raw cloud relay; simple offline JSON file transfer.

---

## 3. Live Dashboard Walkthrough (1:30 – 3:30)

Launch the dashboard:
```bash
streamlit run dashboard/app.py
```

### Step A: System Overview & Pulse
- Point to real-time KPI cards: Total captured notifications, High-priority alerts, Actions detected, and Duplicates grouped.
- Show the **Priority Distribution** and **Category Distribution** charts.
- Highlight the **Needs Immediate Attention** panel displaying high-priority items at a glance.

### Step B: Smart Inbox & Traceable Explanations
- Navigate to **Smart Inbox**.
- Filter by `High` priority or search for an action item.
- Expand an urgent item:
  - Show the predicted category (`action_required`) and confidence score.
  - Point out the extracted deadline and call-to-action.
  - **Key Feature**: Inspect the **Traceable Reasons Box**:
    - *"An explicit action request with an attached deadline was identified."*
    - *"Approaching deadline within 24 hours."*
    - *"High importance assigned to productivity/financial app."*
  - Explain that the priority score is **deterministic and auditable**, not a black box.

### Step C: Action Center & Human-in-the-Loop Feedback
- Switch to the **Action Center**:
  - Display extracted tasks with time-remaining countdowns.
  - Mark a task as completed without performing destructive actions on the user's behalf.
- Switch to **Notification Details**:
  - Demonstrate correcting a category or adjusting a priority level.
  - Show that feedback is saved immediately into SQLite for active learning.

### Step D: Duplicate Clustering
- Open the **Duplicate Center**:
  - Show how 3 repetitive marketing or banking alerts were automatically clustered into a single cluster while preserving every underlying source record.

---

## 4. Rigorous Model Evaluation & Privacy Controls (3:30 – 4:30)

- Open **Analytics & Evaluation** $\rightarrow$ **Model Evaluation Tab**:
  - Show the held-out test set metrics:
    - **Category Accuracy**: ~97.6%
    - **Macro-F1**: 0.943 vs Baseline 0.699 (+0.244 improvement)
    - **High-Priority Precision**: 100%
    - **Median Latency**: ~6.7 milliseconds (ultra-fast offline inference)
  - Display the interactive **Confusion Matrix Heatmap**.
- Open **Settings & Privacy**:
  - Demonstrate the one-click **JSON/CSV Data Export**.
  - Show the **Purge Stored Data** button with user confirmation dialog.

---

## 5. Summary & Conclusion (4:30 – 5:00)

- **Technical Highlights**:
  - Kotlin Android listener $\rightarrow$ Schema-validated JSON $\rightarrow$ Scikit-learn TF-IDF + Logistic Regression $\rightarrow$ Deterministic Priority Formula $\rightarrow$ Parameterized SQLite $\rightarrow$ Streamlit/Plotly UI.
  - 32 automated tests passing with 100% test coverage.
  - Fully offline; zero cloud API subscriptions; zero privacy leaks.
