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
});
