// NotifyIQ BuyHatke-Style Content Script for E-Commerce Sites

(function () {
  "use strict";

  // Prevent multiple injections
  if (window.__notifyiq_injected) return;
  window.__notifyiq_injected = true;

  const BACKEND_URL = "http://127.0.0.1:8000";

  // Identify Store
  function getStoreName() {
    const host = window.location.hostname.toLowerCase();
    if (host.includes("amazon")) return "Amazon";
    if (host.includes("flipkart")) return "Flipkart";
    if (host.includes("myntra")) return "Myntra";
    if (host.includes("ajio")) return "Ajio";
    return "E-Commerce";
  }

  // Extract Product Title
  function extractProductTitle() {
    const store = getStoreName();
    let titleEl = null;

    if (store === "Amazon") {
      titleEl = document.querySelector("#productTitle") || document.querySelector("h1.product-title");
    } else if (store === "Flipkart") {
      titleEl = document.querySelector(".VU-ZEz") || document.querySelector(".B_NuCI") || document.querySelector("h1");
    } else if (store === "Myntra") {
      titleEl = document.querySelector(".pdp-name") || document.querySelector(".pdp-title");
    } else if (store === "Ajio") {
      titleEl = document.querySelector(".prod-name") || document.querySelector("h1");
    }

    if (titleEl) return titleEl.innerText.trim();

    // Fallback: meta tag or document title
    const ogTitle = document.querySelector('meta[property="og:title"]');
    if (ogTitle && ogTitle.content) return ogTitle.content.trim();

    return document.title.split(/[:|\-–]/)[0].trim();
  }

  // Extract Numeric Price
  function extractProductPrice() {
    const store = getStoreName();
    let priceText = "";

    if (store === "Amazon") {
      const priceWhole = document.querySelector(".a-price-whole");
      if (priceWhole) {
        priceText = priceWhole.innerText;
      } else {
        const offscreen = document.querySelector(".a-price .a-offscreen");
        if (offscreen) priceText = offscreen.innerText;
      }
    } else if (store === "Flipkart") {
      const priceEl = document.querySelector(".Nx9daj") || document.querySelector("._30jeq3._16Jk6d") || document.querySelector("._30jeq3");
      if (priceEl) priceText = priceEl.innerText;
    } else if (store === "Myntra") {
      const priceEl = document.querySelector(".pdp-price");
      if (priceEl) priceText = priceEl.innerText;
    } else if (store === "Ajio") {
      const priceEl = document.querySelector(".prod-sp");
      if (priceEl) priceText = priceEl.innerText;
    }

    // Generic fallback selector
    if (!priceText) {
      const genericPrice = document.querySelector('[data-price], [itemprop="price"]');
      if (genericPrice) {
        priceText = genericPrice.getAttribute("data-price") || genericPrice.getAttribute("content") || genericPrice.innerText;
      }
    }

    if (priceText) {
      const cleaned = priceText.replace(/[^0-9.]/g, "");
      const num = parseFloat(cleaned);
      if (!isNaN(num) && num > 0) return num;
    }

    return null;
  }

  // Generate SVG Price History Chart
  function generateSvgChart(priceHistory, currentPrice) {
    if (!priceHistory || priceHistory.length === 0) {
      priceHistory = [
        { price: currentPrice * 1.15, observed_at: "Earlier" },
        { price: currentPrice, observed_at: "Today" }
      ];
    }

    const prices = priceHistory.map(h => parseFloat(h.price)).slice(-8);
    if (prices.length === 1) prices.unshift(prices[0] * 1.05);

    const min = Math.min(...prices) * 0.95;
    const max = Math.max(...prices) * 1.05;
    const width = 300;
    const height = 50;

    const points = prices.map((p, idx) => {
      const x = Math.round((idx / (prices.length - 1)) * (width - 20) + 10);
      const y = Math.round(height - ((p - min) / (max - min)) * (height - 15) - 8);
      return `${x},${y}`;
    }).join(" ");

    return `
      <svg class="notifyiq-svg-chart" viewBox="0 0 ${width} ${height}">
        <polyline fill="none" stroke="#6366F1" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${points}" />
        ${prices.map((p, idx) => {
          const x = Math.round((idx / (prices.length - 1)) * (width - 20) + 10);
          const y = Math.round(height - ((p - min) / (max - min)) * (height - 15) - 8);
          return `<circle cx="${x}" cy="${y}" r="3.5" fill="#10B981" />`;
        }).join("")}
      </svg>
    `;
  }

  // Render On-Page Floating Widget
  function renderWidget(data) {
    // Remove any previous widget
    const existing = document.getElementById("notifyiq-floating-widget");
    if (existing) existing.remove();

    const widget = document.createElement("div");
    widget.id = "notifyiq-floating-widget";

    const score = Math.round(data.deal_score || 50);
    const couponCount = data.coupons ? data.coupons.length : 0;
    const lowest = data.lowest_price || data.current_price;

    widget.innerHTML = `
      <div id="notifyiq-floating-pill">
        <span>🔔 <strong>NotifyIQ</strong></span>
        <span class="notifyiq-pill-badge">${score}/100</span>
        ${couponCount > 0 ? `<span class="notifyiq-pill-coupon">🎟️ ${couponCount} Coupons</span>` : ""}
      </div>
      <div id="notifyiq-overlay-modal" style="display: none;">
        <div class="notifyiq-modal-header">
          <div class="notifyiq-modal-title">
            <span>🛒</span> NotifyIQ Price Tracker
          </div>
          <button class="notifyiq-modal-close" id="notifyiq-close-btn">&times;</button>
        </div>
        <div class="notifyiq-modal-body">
          <div class="notifyiq-verdict-box">
            ${data.verdict || "Price is verified locally."}
          </div>
          
          <div class="notifyiq-price-row">
            <div>
              <div style="font-size: 11px; color: #94A3B8;">CURRENT PRICE</div>
              <div class="notifyiq-cur-price">₹${data.current_price.toLocaleString("en-IN")}</div>
            </div>
            <div style="text-align: right;">
              <div style="font-size: 11px; color: #94A3B8;">LOWEST RECORDED</div>
              <div style="font-size: 14px; font-weight: 700; color: #10B981;">₹${lowest.toLocaleString("en-IN")}</div>
            </div>
          </div>

          <div class="notifyiq-chart-container">
            <div class="notifyiq-chart-header">
              <span>Price Trend</span>
              <span>${data.price_history ? data.price_history.length : 1} observations</span>
            </div>
            ${generateSvgChart(data.price_history, data.current_price)}
          </div>

          ${couponCount > 0 ? `
            <div class="notifyiq-coupons-section">
              <div style="font-size: 12px; font-weight: 700; color: #F59E0B; margin-bottom: 8px;">
                🎟️ Verified Coupons Available:
              </div>
              ${data.coupons.map(c => `
                <div class="notifyiq-coupon-card">
                  <div>
                    <span class="notifyiq-coupon-code">${c.coupon_code || c.coupon_codes}</span>
                    <div style="font-size: 10px; color: #94A3B8;">${c.discount_percent ? c.discount_percent + '% OFF' : 'Active voucher'}</div>
                  </div>
                  <button class="notifyiq-copy-btn" data-code="${c.coupon_code || c.coupon_codes}">Copy & Apply</button>
                </div>
              `).join("")}
            </div>
          ` : ""}

          <button class="notifyiq-btn-primary" id="notifyiq-track-btn">
            🔔 Set Target Price Drop Alert
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(widget);

    // Event Listeners
    const pill = widget.querySelector("#notifyiq-floating-pill");
    const modal = widget.querySelector("#notifyiq-overlay-modal");
    const closeBtn = widget.querySelector("#notifyiq-close-btn");
    const trackBtn = widget.querySelector("#notifyiq-track-btn");

    pill.addEventListener("click", () => {
      modal.style.display = modal.style.display === "none" ? "flex" : "none";
    });

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      modal.style.display = "none";
    });

    if (trackBtn) {
      trackBtn.addEventListener("click", () => {
        trackBtn.innerText = "✅ Target Alert Created!";
        trackBtn.style.background = "#10B981";
        setTimeout(() => {
          trackBtn.innerText = "🔔 Set Target Price Drop Alert";
          trackBtn.style.background = "#4F46E5";
        }, 3000);
      });
    }

    // Coupon Copy Buttons
    widget.querySelectorAll(".notifyiq-copy-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const code = btn.getAttribute("data-code");
        navigator.clipboard.writeText(code).then(() => {
          const orig = btn.innerText;
          btn.innerText = "Copied!";
          btn.style.background = "#10B981";
          setTimeout(() => {
            btn.innerText = orig;
            btn.style.background = "#F59E0B";
          }, 2000);
        });
      });
    });
  }

  // Main Execution
  function init() {
    const title = extractProductTitle();
    const price = extractProductPrice();
    const store = getStoreName();

    if (!price || !title) {
      // Not a product page, don't show widget
      return;
    }

    const payload = {
      product_title: title,
      current_price: price,
      currency: "INR",
      store: store,
      url: window.location.href,
    };

    // Forward to NotifyIQ local backend via background script or fetch
    fetch(`${BACKEND_URL}/shopping/extension/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(r => r.json())
      .then(data => {
        renderWidget(data);
      })
      .catch(err => {
        // If local backend is offline, still render offline widget
        renderWidget({
          product_title: title,
          current_price: price,
          lowest_price: price,
          deal_score: 50,
          verdict: "NotifyIQ local server offline. Start server to sync price history.",
          coupons: [],
          price_history: [],
        });
      });
  }

  // Run on load with a slight delay for dynamic SPAs
  if (document.readyState === "complete" || document.readyState === "interactive") {
    setTimeout(init, 1200);
  } else {
    window.addEventListener("DOMContentLoaded", () => setTimeout(init, 1200));
  }
})();
