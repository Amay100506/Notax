// NotifyIQ Popup Controller v1.1

let BACKEND_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = "http://localhost:8501";

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const statusEl = document.getElementById("backend-status");
  const digestGreetingEl = document.getElementById("digest-greeting");
  const digestOverloadBadge = document.getElementById("digest-overload-badge");
  const digestSummaryEl = document.getElementById("digest-summary");
  const briefingUrgentEl = document.getElementById("briefing-urgent-count");
  const briefingPendingActionsEl = document.getElementById("briefing-pending-actions");
  
  const actionsListEl = document.getElementById("actions-list");
  const actionsCounterEl = document.getElementById("actions-counter");

  const dealsCountEl = document.getElementById("active-deals-count");
  const couponsCountEl = document.getElementById("coupons-count");
  const couponsListEl = document.getElementById("coupons-list");

  const backendInput = document.getElementById("backend-url-input");
  const saveBackendBtn = document.getElementById("save-backend-url-btn");
  const tgStatusBadge = document.getElementById("tg-status-badge");
  const dcStatusBadge = document.getElementById("dc-status-badge");
  const openDashboardBtn = document.getElementById("open-dashboard-btn");

  // Tab Switching
  const tabs = document.querySelectorAll(".nav-tab");
  const panes = document.querySelectorAll(".tab-pane");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      panes.forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const target = document.getElementById(tab.getAttribute("data-tab"));
      if (target) target.classList.add("active");
    });
  });

  // Load configured backend URL from storage
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(["backendUrl"], (data) => {
      if (data && data.backendUrl) {
        BACKEND_URL = data.backendUrl;
        if (backendInput) backendInput.value = BACKEND_URL;
      }
      fetchAllData();
    });
  } else {
    fetchAllData();
  }

  // Save backend URL
  if (saveBackendBtn) {
    saveBackendBtn.addEventListener("click", () => {
      const val = (backendInput.value || "").trim().replace(/\/$/, "");
      if (val) {
        BACKEND_URL = val;
        if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({ backendUrl: val }, () => {
            saveBackendBtn.innerText = "Saved!";
            saveBackendBtn.style.background = "#10B981";
            setTimeout(() => {
              saveBackendBtn.innerText = "Save";
              saveBackendBtn.style.background = "#6366F1";
            }, 1500);
            fetchAllData();
          });
        }
      }
    });
  }

  // Open Full Dashboard
  if (openDashboardBtn) {
    openDashboardBtn.addEventListener("click", () => {
      if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.create) {
        chrome.tabs.create({ url: DASHBOARD_URL });
      } else {
        window.open(DASHBOARD_URL, "_blank");
      }
    });
  }

  // Master fetch function
  function fetchAllData() {
    // 1. Health check
    fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(() => {
        statusEl.innerText = "Online";
        statusEl.className = "status-indicator status-online";
        loadBriefing();
        loadActions();
        loadShopping();
        loadWebhooks();
      })
      .catch(() => {
        statusEl.innerText = "Offline";
        statusEl.className = "status-indicator status-offline";
        if (digestSummaryEl) {
          digestSummaryEl.innerText = "Backend server offline. Please start NotifyIQ backend or check settings.";
        }
        if (actionsListEl) {
          actionsListEl.innerHTML = '<div class="loading-text">Server offline. Ensure backend is running.</div>';
        }
        if (couponsListEl) {
          couponsListEl.innerHTML = '<div class="loading-text">Server offline.</div>';
        }
      });
  }

  // 2. Load Daily Digest & Briefing
  function loadBriefing() {
    fetch(`${BACKEND_URL}/analytics/digest`, { signal: AbortSignal.timeout(4000) })
      .then(r => r.json())
      .then(digest => {
        if (digestGreetingEl) digestGreetingEl.innerText = digest.greeting || "Executive Briefing";
        if (digestSummaryEl) digestSummaryEl.innerText = digest.summary || "No notifications recorded yet today.";
        
        if (digestOverloadBadge) {
          const score = Math.round(digest.overload_score || 0);
          digestOverloadBadge.innerText = `${score}/100 ${digest.overload_label || "Score"}`;
          if (score >= 60) {
            digestOverloadBadge.classList.add("high");
          } else {
            digestOverloadBadge.classList.remove("high");
          }
        }

        if (briefingUrgentEl) briefingUrgentEl.innerText = digest.urgent_count ?? 0;
        if (briefingPendingActionsEl) briefingPendingActionsEl.innerText = digest.pending_actions_count ?? 0;
      })
      .catch(err => {
        console.warn("Failed to load digest:", err);
      });
  }

  // 3. Load Action Items & Calendar Sync Links
  function loadActions() {
    fetch(`${BACKEND_URL}/actions?status=open`, { signal: AbortSignal.timeout(4000) })
      .then(r => r.json())
      .then(actions => {
        if (actionsCounterEl) actionsCounterEl.innerText = actions ? actions.length : 0;
        if (!actions || actions.length === 0) {
          actionsListEl.innerHTML = '<div class="loading-text">🎉 No pending actions! All caught up.</div>';
          return;
        }

        actionsListEl.innerHTML = actions.map(act => {
          const deadline = act.deadline_at 
            ? `⏳ ${new Date(act.deadline_at).toLocaleDateString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`
            : "No explicit deadline";

          return `
            <div class="action-card" id="act-card-${act.id}">
              <div class="action-title">${escapeHtml(act.action_text || "Action needed")}</div>
              <div class="action-meta">
                <span>📱 ${escapeHtml(act.source_app || "Notification")}</span>
                <span class="action-deadline">${deadline}</span>
              </div>
              <div class="action-btns">
                <button class="btn-cal" data-id="${act.id}" data-type="google">📅 Google</button>
                <button class="btn-cal" data-id="${act.id}" data-type="outlook">📧 Outlook</button>
                <button class="btn-cal" data-id="${act.id}" data-type="ics">📥 .ics</button>
                <button class="btn-done" data-id="${act.id}">✓ Done</button>
              </div>
            </div>
          `;
        }).join("");

        // Attach action button handlers
        actionsListEl.querySelectorAll(".btn-cal").forEach(btn => {
          btn.addEventListener("click", () => {
            const actId = btn.getAttribute("data-id");
            const calType = btn.getAttribute("data-type");

            if (calType === "ics") {
              // Direct download
              const icsUrl = `${BACKEND_URL}/actions/${actId}/calendar.ics`;
              if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.create) {
                chrome.tabs.create({ url: icsUrl });
              } else {
                window.open(icsUrl, "_blank");
              }
              return;
            }

            // Fetch web calendar links
            fetch(`${BACKEND_URL}/actions/${actId}/calendar-links`)
              .then(r => r.json())
              .then(links => {
                const targetUrl = calType === "google" ? links.google_calendar_url : links.outlook_calendar_url;
                if (targetUrl) {
                  if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.create) {
                    chrome.tabs.create({ url: targetUrl });
                  } else {
                    window.open(targetUrl, "_blank");
                  }
                }
              })
              .catch(() => alert("Could not generate calendar link."));
          });
        });

        actionsListEl.querySelectorAll(".btn-done").forEach(btn => {
          btn.addEventListener("click", () => {
            const actId = btn.getAttribute("data-id");
            fetch(`${BACKEND_URL}/actions/${actId}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ status: "completed" })
            })
            .then(r => r.json())
            .then(() => {
              const card = document.getElementById(`act-card-${actId}`);
              if (card) {
                card.style.opacity = "0.4";
                card.style.pointerEvents = "none";
                setTimeout(() => card.remove(), 400);
              }
              loadBriefing();
            })
            .catch(() => alert("Failed to update status."));
          });
        });
      })
      .catch(err => {
        console.warn("Failed to load actions:", err);
        actionsListEl.innerHTML = '<div class="loading-text">Failed to fetch action items.</div>';
      });
  }

  // 4. Load Shopping Summary & Store Coupons
  function loadShopping() {
    fetch(`${BACKEND_URL}/shopping/summary`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(summary => {
        if (dealsCountEl) dealsCountEl.innerText = summary.active_deals_count || 0;
        if (couponsCountEl) couponsCountEl.innerText = summary.coupons_found || 0;
      })
      .catch(() => {
        if (dealsCountEl) dealsCountEl.innerText = "0";
        if (couponsCountEl) couponsCountEl.innerText = "0";
      });

    fetch(`${BACKEND_URL}/shopping/coupons`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(coupons => {
        if (!coupons || coupons.length === 0) {
          couponsListEl.innerHTML = '<div class="loading-text">No store coupons recorded yet.</div>';
          return;
        }

        couponsListEl.innerHTML = coupons.slice(0, 6).map(c => {
          const code = c.coupon_code || c.coupon_codes;
          return `
            <div class="coupon-row">
              <div>
                <span class="coupon-code-text">${escapeHtml(code)}</span>
                <span style="color: #94A3B8; font-size: 10px; margin-left: 4px;">${c.discount_percent ? c.discount_percent + '% OFF' : ''}</span>
              </div>
              <button class="coupon-copy-btn" data-code="${escapeHtml(code)}">Copy</button>
            </div>
          `;
        }).join("");

        couponsListEl.querySelectorAll(".coupon-copy-btn").forEach(btn => {
          btn.addEventListener("click", () => {
            const code = btn.getAttribute("data-code");
            navigator.clipboard.writeText(code).then(() => {
              const orig = btn.innerText;
              btn.innerText = "Copied!";
              btn.style.background = "#10B981";
              setTimeout(() => {
                btn.innerText = orig;
                btn.style.background = "#F59E0B";
              }, 1500);
            });
          });
        });
      })
      .catch(() => {
        couponsListEl.innerHTML = '<div class="loading-text">No coupons detected.</div>';
      });
  }

  // 5. Load Webhooks Config
  function loadWebhooks() {
    fetch(`${BACKEND_URL}/settings/webhooks`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(cfg => {
        if (tgStatusBadge) {
          if (cfg.has_telegram && cfg.webhooks_enabled) {
            tgStatusBadge.innerText = "Telegram: Connected";
            tgStatusBadge.classList.add("active");
          } else {
            tgStatusBadge.innerText = "Telegram: Not Configured";
            tgStatusBadge.classList.remove("active");
          }
        }
        if (dcStatusBadge) {
          if (cfg.has_discord && cfg.webhooks_enabled) {
            dcStatusBadge.innerText = "Discord: Connected";
            dcStatusBadge.classList.add("active");
          } else {
            dcStatusBadge.innerText = "Discord: Not Configured";
            dcStatusBadge.classList.remove("active");
          }
        }
      })
      .catch(() => {
        if (tgStatusBadge) tgStatusBadge.innerText = "Telegram: Unknown";
        if (dcStatusBadge) dcStatusBadge.innerText = "Discord: Unknown";
      });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
});