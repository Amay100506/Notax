// NotifyIQ Popup Controller

const BACKEND_URL = "http://127.0.0.1:8000";
const DASHBOARD_URL = "http://localhost:8501";

document.addEventListener("DOMContentLoaded", () => {
  const statusEl = document.getElementById("backend-status");
  const dealsCountEl = document.getElementById("active-deals-count");
  const couponsCountEl = document.getElementById("coupons-count");
  const couponsListEl = document.getElementById("coupons-list");
  const openDashboardBtn = document.getElementById("open-dashboard-btn");

  // Check Backend Status
  fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(3000) })
    .then(r => r.json())
    .then(health => {
      statusEl.innerText = "Online";
      statusEl.className = "status-indicator status-online";

      // Load Shopping Summary
      return fetch(`${BACKEND_URL}/shopping/summary`);
    })
    .then(r => r.json())
    .then(summary => {
      dealsCountEl.innerText = summary.active_deals_count || 0;
      couponsCountEl.innerText = summary.coupons_found || 0;
    })
    .catch(() => {
      statusEl.innerText = "Offline";
      statusEl.className = "status-indicator status-offline";
      dealsCountEl.innerText = "0";
      couponsCountEl.innerText = "0";
    });

  // Load Coupons
  fetch(`${BACKEND_URL}/shopping/coupons`, { signal: AbortSignal.timeout(3000) })
    .then(r => r.json())
    .then(coupons => {
      if (!coupons || coupons.length === 0) {
        couponsListEl.innerHTML = '<div class="loading-text">No coupons detected yet.</div>';
        return;
      }

      couponsListEl.innerHTML = coupons.slice(0, 5).map(c => {
        const code = c.coupon_code || c.coupon_codes;
        return `
          <div class="coupon-row">
            <div>
              <span class="coupon-code-text">${code}</span>
              <span style="color: #94A3B8; font-size: 10px;">${c.discount_percent ? c.discount_percent + '% OFF' : ''}</span>
            </div>
            <button class="coupon-copy-btn" data-code="${code}">Copy</button>
          </div>
        `;
      }).join("");

      // Add Copy handlers
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
      couponsListEl.innerHTML = '<div class="loading-text">Connect to local server to view coupons.</div>';
    });

  // Open Dashboard Link
  openDashboardBtn.addEventListener("click", () => {
    chrome.tabs.create({ url: DASHBOARD_URL });
  });
});
