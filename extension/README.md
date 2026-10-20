# NotifyIQ — BuyHatke-Style Smart Shopping Browser Extension

This is a Manifest V3 browser extension for Google Chrome, Microsoft Edge, Brave, and Chromium browsers. It overlays on top of e-commerce websites (Amazon, Flipkart, Myntra, Ajio) to provide:
1. **Live Price Comparison & Price Trend Graphs** (matching historical notification prices).
2. **AI Deal Quality Scoring** (0 to 100).
3. **Automated Coupon Detection & 1-Click Copy & Apply**.
4. **Target Price Drop Alert Setting** directly synced to your local NotifyIQ AI backend.
5. **100% Local & Privacy-Preserving** — zero external telemetry, all data stays in your local SQLite database.

---

## 🚀 How to Install in Chrome or Microsoft Edge

1. Open your browser and navigate to:
   - **Chrome**: `chrome://extensions`
   - **Edge**: `edge://extensions`
   - **Brave**: `brave://extensions`
2. Enable **"Developer mode"** (toggle in the top-right corner).
3. Click the **"Load unpacked"** button.
4. Select the `extension` folder located at:
   ```
   C:\Users\Amay\Downloads\VR-Headset-main\extension
   ```
5. The **NotifyIQ Shopping Assistant** icon will appear in your browser toolbar!

---

## 🛒 How to Use on E-Commerce Sites

1. Make sure the NotifyIQ backend is running (`python -m uvicorn backend.main:app --port 8000`).
2. Open any product page on:
   - **Amazon India**: `https://www.amazon.in`
   - **Flipkart**: `https://www.flipkart.com`
   - **Myntra**: `https://www.myntra.com`
3. A floating **"🔔 NotifyIQ [Score/100] [Coupons]"** badge will automatically appear in the bottom-right corner!
4. Click the badge to expand:
   - Price trend chart.
   - Lowest recorded price.
   - Active coupons with **Copy & Apply**.
   - Price drop alert subscription.
