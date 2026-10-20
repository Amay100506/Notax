// NotifyIQ Extension Service Worker (Manifest V3)

let BACKEND_URL = "http://127.0.0.1:8000";

// Listen for installation
chrome.runtime.onInstalled.addListener(() => {
  console.log("NotifyIQ Smart Shopping & Price Tracker extension installed.");
  chrome.storage.local.get(["backendUrl"], (data) => {
    if (!data || !data.backendUrl) {
      chrome.storage.local.set({
        backendUrl: BACKEND_URL,
        alertsEnabled: true,
      });
    } else {
      BACKEND_URL = data.backendUrl;
    }
  });

  // Create background price check alarm every 15 minutes
  if (chrome.alarms) {
    chrome.alarms.create("notifyiq_price_check", { periodInMinutes: 15 });
  }
});

// Periodic background alarm listener
if (chrome.alarms) {
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "notifyiq_price_check") {
      checkActivePriceAlerts();
    }
  });
}

function checkActivePriceAlerts() {
  chrome.storage.local.get(["backendUrl", "price_alerts"], (res) => {
    const url = res.backendUrl || BACKEND_URL;
    const alerts = res.price_alerts || [];
    if (alerts.length === 0) return;

    // Check each alert against backend price history
    alerts.forEach((alertItem, idx) => {
      fetch(`${url}/shopping/price-history/${encodeURIComponent(alertItem.product_title)}`)
        .then(r => r.json())
        .then(history => {
          if (!history || history.length === 0) return;
          const latest = history[0];
          const latestPrice = parseFloat(latest.price);
          const target = parseFloat(alertItem.target_price);

          if (latestPrice <= target && !alertItem.notified) {
            // Trigger native notification
            if (chrome.notifications) {
              chrome.notifications.create(`price_drop_${idx}_${Date.now()}`, {
                type: "basic",
                iconUrl: "icons/icon-48.png",
                title: "🔥 PRICE DROP ALERT: Target Reached!",
                message: `"${alertItem.product_title.slice(0, 35)}..." dropped to ₹${latestPrice.toLocaleString("en-IN")} (Target was ₹${target.toLocaleString("en-IN")})!`,
                priority: 2,
              });
            }
            alertItem.notified = true;
            chrome.storage.local.set({ price_alerts: alerts });
          }
        })
        .catch(() => {});
    });
  });
}

// Notification click opens product URL if available
if (chrome.notifications) {
  chrome.notifications.onClicked.addListener((notifId) => {
    chrome.storage.local.get(["price_alerts"], (res) => {
      const alerts = res.price_alerts || [];
      if (alerts.length > 0 && alerts[0].url) {
        chrome.tabs.create({ url: alerts[0].url });
      }
    });
  });
}

// Message listener from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "CHECK_BACKEND_STATUS") {
    fetch(`${BACKEND_URL}/health`)
      .then(r => r.json())
      .then(data => sendResponse({ online: true, data: data }))
      .catch(err => sendResponse({ online: false, error: err.message }));
    return true;
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
        // Trigger immediate confirmation notification
        if (chrome.notifications) {
          chrome.notifications.create({
            type: "basic",
            iconUrl: "icons/icon-48.png",
            title: "🎯 NotifyIQ Price Drop Alert Set!",
            message: `Tracking "${(alertItem.product_title || '').slice(0, 30)}...". We'll notify you when it drops below ₹${alertItem.target_price.toLocaleString('en-IN')}!`,
            priority: 2,
          });
        }
        sendResponse({ success: true, count: alerts.length });
      });
    });
    return true;
  }

  if (request.type === "GET_LOCAL_ALERTS") {
    chrome.storage.local.get(["price_alerts"], (res) => {
      sendResponse({ alerts: res.price_alerts || [] });
    });
    return true;
  }
});