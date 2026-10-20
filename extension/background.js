// NotifyIQ Extension Service Worker (Manifest V3)

const BACKEND_URL = "http://127.0.0.1:8000";

// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log("NotifyIQ Smart Shopping & Price Tracker extension installed.");
  chrome.storage.local.set({
    backendUrl: BACKEND_URL,
    alertsEnabled: true,
  });
});

// Message listener from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "CHECK_BACKEND_STATUS") {
    fetch(`${BACKEND_URL}/health`)
      .then(r => r.json())
      .then(data => sendResponse({ online: true, data: data }))
      .catch(err => sendResponse({ online: false, error: err.message }));
    return true; // Keep message channel open for async response
  }

  if (request.type === "FETCH_COUPONS") {
    fetch(`${BACKEND_URL}/shopping/coupons`)
      .then(r => r.json())
      .then(coupons => sendResponse({ coupons }))
      .catch(err => sendResponse({ coupons: [] }));
    return true;
  }

  if (request.type === "CREATE_PRICE_ALERT") {
    const alertItem = request.payload;
    chrome.storage.local.get(["price_alerts"], (res) => {
      const alerts = res.price_alerts || [];
      alerts.push(alertItem);
      chrome.storage.local.set({ price_alerts: alerts }, () => {
        // Trigger system notification
        if (chrome.notifications) {
          chrome.notifications.create({
            type: "basic",
            iconUrl: "icons/icon-48.png",
            title: "🎯 NotifyIQ Price Drop Alert Set!",
            message: `Tracking "${(alertItem.product_title || '').slice(0, 30)}...". We'll notify you when it drops below ₹${alertItem.target_price}!`,
            priority: 2,
          });
        }
        sendResponse({ success: true, count: alerts.length });
      });
    });
    return true;
  }
});
