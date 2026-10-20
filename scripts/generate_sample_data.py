"""
Synthetic notification generator for NotifyIQ.
Generates realistic, privacy-safe notifications across 6 categories:
action_required, transactional, social, promotional, system, unknown.
Produces:
- data/training_notifications.csv
- data/evaluation_notifications.csv
- data/sample_notifications.json
- data/shopping_notifications.json
Deterministic with fixed random seed.
"""

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CATEGORIES = [
    "action_required",
    "transactional",
    "social",
    "promotional",
    "system",
    "unknown",
]

# Curated templates for reproducible synthetic data generation
TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "action_required": [
        ("com.google.android.apps.docs", "Document Approval", "Please review and approve the project budget proposal before 5 PM."),
        ("org.edx.mobile", "Assignment Due Soon", "Your assignment for Machine Learning module 3 is due tomorrow at 11:59 PM."),
        ("com.slack", "Channel Mention", "Can you please submit your weekly sprint status report by Friday 6 PM?"),
        ("com.github.android", "Pull Request Review", "Please review pull request #142 for the authentication module."),
        ("com.microsoft.teams", "Action Needed", "Complete the compliance survey before October 25."),
        ("com.bank.secure", "Identity Verification", "Please verify your updated residential address within 24 hours to prevent account freeze."),
        ("com.airbnb.android", "Booking Confirmation", "Please confirm your upcoming reservation details by tonight 8 PM."),
        ("com.coursera.org", "Quiz Deadline", "Quiz 4 expires in 3 hours. Complete it to maintain your grade."),
        ("com.tax.portal", "Filing Reminder", "Please upload your tax declarations and receipts before tomorrow noon."),
        ("com.health.portal", "Appointment Confirmation", "Confirm your dental consultation scheduled for tomorrow at 10:00 AM."),
        ("com.utility.electricity", "Bill Due", "Your electricity bill payment of $84.50 is due by tomorrow 5 PM."),
        ("com.google.android.calendar", "RSVP Required", "Please respond to the invitation for Strategy Sync by 4 PM."),
        ("com.zoom.videomeetings", "Webinar Registration", "Register for the Q4 all-hands session before 3 PM today."),
        ("com.telecom.provider", "SIM KYC Renewal", "Kindly complete your re-verification process within 48 hours."),
        ("com.insurance.policy", "Renewal Notice", "Your vehicle insurance expires in two days. Renew your policy now."),
    ],
    "transactional": [
        ("com.amazon.mShop.android.shopping", "Order Shipped", "Your package with order #98214 is out for delivery today."),
        ("com.bank.secure", "Transaction Alert", "Debited USD 45.20 at Supermarket using card ending 4092 on 19-Oct."),
        ("com.paypal.android.p2pmobile", "Money Received", "You received $120.00 from Alex for the freelance project."),
        ("com.ubercab", "Ride Receipt", "Your trip with Uber on Monday cost $18.50. Thank you for riding."),
        ("com.swiggy.consumer", "Food Out for Delivery", "Your meal from Pizza Hearth is on the way with delivery partner Rahul."),
        ("com.zomato", "Order Delivered", "Enjoy your meal! Order #4489 has been delivered to your door."),
        ("com.airline.fly", "Boarding Pass Ready", "Check-in successful. Your flight AI-202 departs at Terminal 3 Gate 14."),
        ("com.railway.irctc", "Ticket Confirmed", "PNR 2419830214 confirmed. Coach B3 Berth 21."),
        ("com.starbucks.mobile", "Card Reloaded", "Successfully added $25.00 to your digital card."),
        ("com.netflix.mediaclient", "Subscription Billed", "Your monthly subscription fee of $15.99 has been successfully billed."),
        ("com.apple.store", "Receipt for Purchase", "Receipt for iCloud+ 50GB storage plan for $0.99."),
        ("com.dhl.express", "Customs Clearance", "Shipment #38192 cleared customs in transit."),
    ],
    "social": [
        ("com.whatsapp", "Sarah Jenkins", "Hey, are you free for a quick coffee this afternoon?"),
        ("com.instagram.android", "david_k liked your story", "david_k and 4 others reacted to your story."),
        ("com.twitter.android", "New Mention", "TechDaily mentioned you in: 'Exciting AI architectures for edge devices!'"),
        ("com.linkedin.android", "Connection Request", "Michael Chang, Senior ML Engineer, wants to connect with you."),
        ("com.facebook.katana", "Group Update", "5 new posts in Open Source Developers Group today."),
        ("com.telegram.messenger", "Family Chat", "Grandma: Happy birthday! Hope you have a wonderful year ahead!"),
        ("com.discord", "Gaming Guild", "Server announcement: Tournament starts tonight at 9 PM."),
        ("com.reddit.frontpage", "Trending in r/Python", "Check out how to build asynchronous microservices without bloat."),
        ("com.snapchat.android", "Snap from Jessica", "Jessica sent you a snap!"),
        ("com.signal.messenger", "Lucas", "Sent the encrypted notes for the meeting yesterday."),
    ],
    "promotional": [
        ("com.shopping.mega", "MEGA SALE 50% OFF", "Flash sale ends midnight! Use code SAVE50 on fashion and electronics!"),
        ("com.fooddelivery.deals", "Free Delivery Today Only!", "Craving burgers? Order now and get free delivery on all orders over $15!"),
        ("com.travel.booking", "Unbeatable Flight Deals", "Fly to Bali starting at just $299 roundtrip. Book before seats run out!"),
        ("com.fashion.store", "Autumn Collection Dropped", "Explore fresh seasonal styles with exclusive 20% member savings."),
        ("com.gaming.arcade", "Free Coins Bonus!", "Claim your 1,000 free bonus coins by logging into Diamond Quest right now!"),
        ("com.gym.fitness", "New Year Membership Special", "Join today with 0 enrollment fee and get the first month complimentary!"),
        ("com.ott.stream", "Blockbuster Movie Streaming", "Watch the latest action thriller streaming exclusively on StreamMax."),
        ("com.pizza.hut", "Buy 1 Get 1 Free", "Tasty Tuesday is here! Buy any medium pizza and get another free!"),
        ("com.gadgets.direct", "Special Clearance Discount", "Refurbished laptops and smartwatches up to 70% off while supplies last."),
    ],
    "system": [
        ("com.android.systemui", "System Update Ready", "Android 15 security patch is ready to install. Restart to apply."),
        ("com.google.android.gms", "Security Alert", "New sign-in detected on Windows Chrome near Mumbai, India."),
        ("com.android.providers.downloads", "Download Complete", "notifyiq_dataset_v1.zip finished downloading (12.4 MB)."),
        ("com.android.settings", "Low Storage Space", "Less than 1 GB storage remaining. Tap to free up space."),
        ("com.android.bluetooth", "Bluetooth Connected", "Connected to Sony WH-1000XM4 headphones."),
        ("com.android.systemui", "Battery Saver Enabled", "Battery at 15%. Performance optimized to extend battery life."),
        ("com.google.android.apps.authenticator2", "2FA Key Synced", "Cloud backup for two-factor authentication accounts completed."),
        ("com.android.vending", "Apps Updated", "Google Maps and 3 other applications updated successfully."),
        ("com.qualcomm.location", "GPS Active", "Navigation is using precise location in the background."),
    ],
    "unknown": [
        ("com.mystery.service", "Sync Status", "Service ping completed with code 200."),
        ("org.custom.daemon", "", "Daemon heartbeat check ok."),
        ("com.unknown.app", "Test Notification", "12345 67890"),
        ("com.test.debug", "---", "..."),
        ("com.random.internal", "Background Worker", "Task worker id #4802 state transitioned to idle."),
        ("com.legacy.tool", "Log Notice", "Index cache rebuilt in 34ms."),
    ],
}

# Dedicated templates for Indian shopping and commerce ecosystems
SHOPPING_TEMPLATES: dict[str, list[tuple[str, str, str]]] = {
    "action_required": [
        ("net.one97.paytm", "Electricity Bill Due Tomorrow", "Please pay your BESCOM electricity bill of ₹2,180 due tomorrow Oct 20 before 5 PM to prevent late payment penalty."),
        ("com.flipkart.android", "Flipkart Pay Later Due", "Please pay your Flipkart Pay Later monthly bill of ₹3,840 due by tomorrow 11:59 PM to avoid late payment charges."),
        ("com.phonepe.app", "Broadband Bill Reminder", "Your Airtel Xstream Broadband bill of ₹1,179 is due on Oct 21. Pay now to enjoy uninterrupted high-speed internet."),
        ("com.amazon.mShop.android.shopping", "Subscribe & Save Delivery", "Your monthly Subscribe & Save order #402-8871204 will be dispatched on Oct 21. Review items by tomorrow 5 PM."),
        ("com.ril.ajio", "Flash Deal: Ends in 1 Hour!", "Sneakers flash sale! Red Tape & Puma sneakers at flat ₹1,199. Complete your purchase before 7 PM!"),
    ],
    "transactional": [
        ("com.amazon.mShop.android.shopping", "Order Shipped", "Your order #402-1234567 has been shipped. Arriving by Oct 22."),
        ("com.amazon.mShop.android.shopping", "Out for Delivery", "Your package containing OnePlus Nord CE4 is out for delivery today. Track your delivery driver live."),
        ("com.amazon.mShop.android.shopping", "Delivered: Package Handed Off", "Your order #405-9988123 was delivered to resident. Please rate your delivery partner."),
        ("com.amazon.mShop.android.shopping", "Refund Processed", "Refund of ₹2,499 for your returned Philips Air Fryer has been issued to Amazon Pay balance."),
        ("com.flipkart.android", "Out for Delivery", "Flipkart Wishmaster Vikas is arriving with your order OD2910384712 today. Share OTP 5812 at delivery."),
        ("com.flipkart.android", "Order Delivered", "Delivered: Your package containing Puma Walking Shoes was delivered at 2:45 PM. Check your item and submit a review."),
        ("com.flipkart.android", "Flight Booking Confirmed", "Flipkart Flights: PNR #FK83921 confirmed for BLR to DEL on 28-Oct. E-ticket sent to your registered email."),
        ("com.myntra.android", "Order Shipped: Bluedart Express", "Your Myntra order #11982736-2 has been shipped. Track tracking #BD4918204. Estimated delivery by Oct 22."),
        ("com.application.zomato", "Order Out for Delivery", "Your meal from Meghana Foods is on the way! Valet Santosh is arriving at your location in 15 minutes."),
        ("net.one97.paytm", "Cashback Received! ₹75", "Cashback of ₹75 credited to your Paytm Wallet for scanning QR code at Reliance Fresh."),
        ("com.phonepe.app", "Payment Successful: ₹1,850", "Paid ₹1,850 to Cult.fit Gym Membership via UPI Transaction ID T251019143011. Debited from HDFC Bank A/c ending 4012."),
        ("com.ril.ajio", "Order Confirmed: #AJ9812401", "Your order for Dennis Lingo Slim Fit Shirt (₹899) is confirmed. Expected delivery by Thursday, Oct 23."),
        ("com.fsn.nykaa", "Order Shipped: NYK928103", "Your package with The Ordinary Niacinamide Serum has shipped via Blue Dart. Arriving by tomorrow."),
        ("com.meesho.supply", "Out for Delivery", "Your Meesho parcel #MEE448201 is out for delivery today. Cash on delivery amount to pay: ₹349."),
    ],
    "promotional": [
        ("com.amazon.mShop.android.shopping", "Price Drop Alert!", "Price dropped! Sony WH-1000XM5 now ₹22,990 (was ₹29,990). Save ₹7,000!"),
        ("com.amazon.mShop.android.shopping", "Lightning Deal!", "Lightning Deal! Samsung Galaxy M34 at ₹13,999. Offer ends in 2 hours!"),
        ("com.amazon.mShop.android.shopping", "Coupon Applied", "Use code FLAT500 to get ₹500 off on electronics. Valid till midnight."),
        ("com.amazon.mShop.android.shopping", "Wishlist Alert", "Item on your Wishlist is now on sale! boAt Rockerz 450 at ₹1,099"),
        ("com.amazon.mShop.android.shopping", "Great Indian Festival", "Prime Early Deal: Apple iPad (10th Gen) starts at ₹31,999 with additional ₹2,500 SBI card discount."),
        ("com.flipkart.android", "Big Billion Days Starts Tonight!", "BBD Early Access: Apple iPhone 15 at ₹52,999 and Moto Edge 50 at ₹20,999. Sale goes live tonight at 12:00 AM!"),
        ("com.flipkart.android", "SuperCoin Rewards Credited", "You earned 120 SuperCoins on order OD30291823. Redeem your coins now to get ₹250 off on electronics!"),
        ("com.flipkart.android", "Lowest Price Guaranteed!", "Price Comparison: Realme P1 5G is now ₹14,999 on Flipkart — ₹2,000 lower than retail stores. Grab yours today!"),
        ("com.flipkart.android", "Price Crash on Smart TVs", "Samsung 43-inch Crystal 4K TV dropped from ₹42,990 to ₹26,990. Additional ₹1,500 off on Axis Bank credit cards."),
        ("com.myntra.android", "Right to Fashion Sale is LIVE", "50% to 80% OFF on 2 Lakh+ styles! Levi's, Tommy Hilfiger, and Mango on sale. Offer valid till midnight."),
        ("com.myntra.android", "Brand Day: H&M Special", "Flat 40% OFF on all fresh seasonal styles + Extra 15% off with coupon code HM15 on orders above ₹2,499."),
        ("com.myntra.android", "Flat ₹400 Off Coupon", "Use code MYNTRA400 on clothing and footwear to get ₹400 off on minimum purchase of ₹1,999. Valid today only."),
        ("com.myntra.android", "Myntra Insider Notice", "Your 450 Myntra Insider points worth ₹225 will expire in 3 days. Use them on your next fashion order!"),
        ("in.swiggy.android", "Hungry? 50% Off Lunch Deal", "Craving delicious biryani? Use code SWIGGY50 to get 50% off up to ₹100 on orders from top-rated restaurants."),
        ("com.application.zomato", "Dinner Time! Flat 40% Off", "Enjoy tonight's dinner with code ZOMATO40 for 40% off up to ₹80 + Free delivery on orders above ₹199."),
        ("in.swiggy.android", "Free Delivery on Swiggy Instamart", "Free delivery on all grocery and snack orders above ₹99 today only! Get daily essentials delivered in 10 minutes."),
        ("in.swiggy.android", "Swiggy Dineout: Save ₹500", "Dining out tonight? Pay your bill via Swiggy Dineout to unlock flat 25% off up to ₹500 at partnered cafes."),
        ("net.one97.paytm", "Recharge Offer: Flat ₹30 Cashback", "Recharge your Jio or Airtel mobile number with ₹299 or more using code RECHARGE30 to get flat ₹30 cashback."),
        ("com.ril.ajio", "Ajio All Stars Sale is LIVE!", "50-90% Off on Top Brands! Use code STARS1000 for extra ₹1,000 off on orders above ₹3,990."),
        ("com.fsn.nykaa", "Nykaa Pink Friday Sale Sneak Peek", "Exclusive Early Access: Buy 1 Get 1 Free on L'Oreal & Maybelline cosmetics! Offer ends tonight at midnight."),
        ("com.meesho.supply", "Mega Blockbuster Sale!", "Ethnic wear starting from ₹149! Free delivery on your first order + Extra ₹50 off applied at checkout."),
    ],
}

# 40 Curated realistic Indian e-commerce shopping notifications
SHOPPING_NOTIFICATIONS_DATA: list[dict[str, Any]] = [
    # 1. Amazon India (10 notifications: shop-001 through shop-010)
    {
        "schema_version": 1,
        "event_id": "shop-001",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Price Drop Alert!",
        "text": "Price dropped! Sony WH-1000XM5 now ₹22,990 (was ₹29,990). Save ₹7,000!",
        "posted_at": "2025-10-19T09:15:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-002",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Order Shipped",
        "text": "Your order #402-1234567 has been shipped. Arriving by Oct 22.",
        "posted_at": "2025-10-19T10:30:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-003",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Lightning Deal!",
        "text": "Lightning Deal! Samsung Galaxy M34 at ₹13,999. Offer ends in 2 hours!",
        "posted_at": "2025-10-19T11:45:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-004",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Coupon Applied",
        "text": "Use code FLAT500 to get ₹500 off on electronics. Valid till midnight.",
        "posted_at": "2025-10-19T13:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-005",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Wishlist Alert",
        "text": "Item on your Wishlist is now on sale! boAt Rockerz 450 at ₹1,099",
        "posted_at": "2025-10-19T14:10:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-006",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Out for Delivery",
        "text": "Your package containing OnePlus Nord CE4 is out for delivery today. Track your delivery driver live.",
        "posted_at": "2025-10-19T08:30:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-007",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Delivered: Package Handed Off",
        "text": "Your order #405-9988123 was delivered to resident. Please rate your delivery partner.",
        "posted_at": "2025-10-19T15:20:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-008",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Great Indian Festival",
        "text": "Prime Early Deal: Apple iPad (10th Gen) starts at ₹31,999 with additional ₹2,500 SBI card discount.",
        "posted_at": "2025-10-19T16:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-009",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Refund Processed",
        "text": "Refund of ₹2,499 for your returned Philips Air Fryer has been issued to Amazon Pay balance.",
        "posted_at": "2025-10-19T17:15:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-010",
        "package_name": "com.amazon.mShop.android.shopping",
        "title": "Subscribe & Save Delivery",
        "text": "Your monthly Subscribe & Save order #402-8871204 will be dispatched on Oct 21. Review items by tomorrow 5 PM.",
        "posted_at": "2025-10-19T18:00:00+05:30",
        "event_type": "posted",
    },

    # 2. Flipkart (8 notifications: shop-011 through shop-018)
    {
        "schema_version": 1,
        "event_id": "shop-011",
        "package_name": "com.flipkart.android",
        "title": "Big Billion Days Starts Tonight!",
        "text": "BBD Early Access: Apple iPhone 15 at ₹52,999 and Moto Edge 50 at ₹20,999. Sale goes live tonight at 12:00 AM!",
        "posted_at": "2025-10-19T19:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-012",
        "package_name": "com.flipkart.android",
        "title": "SuperCoin Rewards Credited",
        "text": "You earned 120 SuperCoins on order OD30291823. Redeem your coins now to get ₹250 off on electronics!",
        "posted_at": "2025-10-19T11:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-013",
        "package_name": "com.flipkart.android",
        "title": "Lowest Price Guaranteed!",
        "text": "Price Comparison: Realme P1 5G is now ₹14,999 on Flipkart — ₹2,000 lower than retail stores. Grab yours today!",
        "posted_at": "2025-10-19T12:30:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-014",
        "package_name": "com.flipkart.android",
        "title": "Out for Delivery",
        "text": "Flipkart Wishmaster Vikas is arriving with your order OD2910384712 today. Share OTP 5812 at delivery.",
        "posted_at": "2025-10-19T09:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-015",
        "package_name": "com.flipkart.android",
        "title": "Order Delivered",
        "text": "Delivered: Your package containing Puma Walking Shoes was delivered at 2:45 PM. Check your item and submit a review.",
        "posted_at": "2025-10-19T14:50:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-016",
        "package_name": "com.flipkart.android",
        "title": "Price Crash on Smart TVs",
        "text": "Samsung 43-inch Crystal 4K TV dropped from ₹42,990 to ₹26,990. Additional ₹1,500 off on Axis Bank credit cards.",
        "posted_at": "2025-10-19T15:40:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-017",
        "package_name": "com.flipkart.android",
        "title": "Flipkart Pay Later Due",
        "text": "Please pay your Flipkart Pay Later monthly bill of ₹3,840 due by tomorrow 11:59 PM to avoid late payment charges.",
        "posted_at": "2025-10-19T17:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-018",
        "package_name": "com.flipkart.android",
        "title": "Flight Booking Confirmed",
        "text": "Flipkart Flights: PNR #FK83921 confirmed for BLR to DEL on 28-Oct. E-ticket sent to your registered email.",
        "posted_at": "2025-10-19T16:30:00+05:30",
        "event_type": "posted",
    },

    # 3. Myntra (5 notifications: shop-019 through shop-023)
    {
        "schema_version": 1,
        "event_id": "shop-019",
        "package_name": "com.myntra.android",
        "title": "Right to Fashion Sale is LIVE",
        "text": "50% to 80% OFF on 2 Lakh+ styles! Levi's, Tommy Hilfiger, and Mango on sale. Offer valid till midnight.",
        "posted_at": "2025-10-19T09:30:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-020",
        "package_name": "com.myntra.android",
        "title": "Brand Day: H&M Special",
        "text": "Flat 40% OFF on all fresh seasonal styles + Extra 15% off with coupon code HM15 on orders above ₹2,499.",
        "posted_at": "2025-10-19T11:15:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-021",
        "package_name": "com.myntra.android",
        "title": "Flat ₹400 Off Coupon",
        "text": "Use code MYNTRA400 on clothing and footwear to get ₹400 off on minimum purchase of ₹1,999. Valid today only.",
        "posted_at": "2025-10-19T13:45:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-022",
        "package_name": "com.myntra.android",
        "title": "Order Shipped: Bluedart Express",
        "text": "Your Myntra order #11982736-2 has been shipped. Track tracking #BD4918204. Estimated delivery by Oct 22.",
        "posted_at": "2025-10-19T15:10:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-023",
        "package_name": "com.myntra.android",
        "title": "Myntra Insider Notice",
        "text": "Your 450 Myntra Insider points worth ₹225 will expire in 3 days. Use them on your next fashion order!",
        "posted_at": "2025-10-19T18:15:00+05:30",
        "event_type": "posted",
    },

    # 4. Swiggy/Zomato (5 notifications: shop-024 through shop-028)
    {
        "schema_version": 1,
        "event_id": "shop-024",
        "package_name": "in.swiggy.android",
        "title": "Hungry? 50% Off Lunch Deal",
        "text": "Craving delicious biryani? Use code SWIGGY50 to get 50% off up to ₹100 on orders from top-rated restaurants.",
        "posted_at": "2025-10-19T12:15:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-025",
        "package_name": "com.application.zomato",
        "title": "Dinner Time! Flat 40% Off",
        "text": "Enjoy tonight's dinner with code ZOMATO40 for 40% off up to ₹80 + Free delivery on orders above ₹199.",
        "posted_at": "2025-10-19T19:15:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-026",
        "package_name": "in.swiggy.android",
        "title": "Free Delivery on Swiggy Instamart",
        "text": "Free delivery on all grocery and snack orders above ₹99 today only! Get daily essentials delivered in 10 minutes.",
        "posted_at": "2025-10-19T08:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-027",
        "package_name": "com.application.zomato",
        "title": "Order Out for Delivery",
        "text": "Your meal from Meghana Foods is on the way! Valet Santosh is arriving at your location in 15 minutes.",
        "posted_at": "2025-10-19T13:10:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-028",
        "package_name": "in.swiggy.android",
        "title": "Swiggy Dineout: Save ₹500",
        "text": "Dining out tonight? Pay your bill via Swiggy Dineout to unlock flat 25% off up to ₹500 at partnered cafes.",
        "posted_at": "2025-10-19T18:40:00+05:30",
        "event_type": "posted",
    },

    # 5. Paytm/PhonePe (5 notifications: shop-029 through shop-033)
    {
        "schema_version": 1,
        "event_id": "shop-029",
        "package_name": "net.one97.paytm",
        "title": "Cashback Received! ₹75",
        "text": "Cashback of ₹75 credited to your Paytm Wallet for scanning QR code at Reliance Fresh.",
        "posted_at": "2025-10-19T10:50:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-030",
        "package_name": "com.phonepe.app",
        "title": "Payment Successful: ₹1,850",
        "text": "Paid ₹1,850 to Cult.fit Gym Membership via UPI Transaction ID T251019143011. Debited from HDFC Bank A/c ending 4012.",
        "posted_at": "2025-10-19T14:30:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-031",
        "package_name": "net.one97.paytm",
        "title": "Electricity Bill Due Tomorrow",
        "text": "Please pay your BESCOM electricity bill of ₹2,180 due tomorrow Oct 20 before 5 PM to prevent late payment penalty.",
        "posted_at": "2025-10-19T09:20:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-032",
        "package_name": "com.phonepe.app",
        "title": "Broadband Bill Reminder",
        "text": "Your Airtel Xstream Broadband bill of ₹1,179 is due on Oct 21. Pay now to enjoy uninterrupted high-speed internet.",
        "posted_at": "2025-10-19T16:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-033",
        "package_name": "net.one97.paytm",
        "title": "Recharge Offer: Flat ₹30 Cashback",
        "text": "Recharge your Jio or Airtel mobile number with ₹299 or more using code RECHARGE30 to get flat ₹30 cashback.",
        "posted_at": "2025-10-19T17:45:00+05:30",
        "event_type": "posted",
    },

    # 6. Other apps (7 notifications: shop-034 through shop-040)
    {
        "schema_version": 1,
        "event_id": "shop-034",
        "package_name": "com.ril.ajio",
        "title": "Ajio All Stars Sale is LIVE!",
        "text": "50-90% Off on Top Brands! Use code STARS1000 for extra ₹1,000 off on orders above ₹3,990.",
        "posted_at": "2025-10-19T10:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-035",
        "package_name": "com.fsn.nykaa",
        "title": "Nykaa Pink Friday Sale Sneak Peek",
        "text": "Exclusive Early Access: Buy 1 Get 1 Free on L'Oreal & Maybelline cosmetics! Offer ends tonight at midnight.",
        "posted_at": "2025-10-19T11:30:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-036",
        "package_name": "com.meesho.supply",
        "title": "Mega Blockbuster Sale!",
        "text": "Ethnic wear starting from ₹149! Free delivery on your first order + Extra ₹50 off applied at checkout.",
        "posted_at": "2025-10-19T12:00:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-037",
        "package_name": "com.ril.ajio",
        "title": "Order Confirmed: #AJ9812401",
        "text": "Your order for Dennis Lingo Slim Fit Shirt (₹899) is confirmed. Expected delivery by Thursday, Oct 23.",
        "posted_at": "2025-10-19T14:40:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-038",
        "package_name": "com.fsn.nykaa",
        "title": "Order Shipped: NYK928103",
        "text": "Your package with The Ordinary Niacinamide Serum has shipped via Blue Dart. Arriving by tomorrow.",
        "posted_at": "2025-10-19T15:50:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-039",
        "package_name": "com.meesho.supply",
        "title": "Out for Delivery",
        "text": "Your Meesho parcel #MEE448201 is out for delivery today. Cash on delivery amount to pay: ₹349.",
        "posted_at": "2025-10-19T09:40:00+05:30",
        "event_type": "posted",
    },
    {
        "schema_version": 1,
        "event_id": "shop-040",
        "package_name": "com.ril.ajio",
        "title": "Flash Deal: Ends in 1 Hour!",
        "text": "Sneakers flash sale! Red Tape & Puma sneakers at flat ₹1,199. Complete your purchase before 7 PM!",
        "posted_at": "2025-10-19T18:00:00+05:30",
        "event_type": "posted",
    },
]


def generate_shopping_dataset() -> list[dict[str, Any]]:
    """
    Returns 40 curated, realistic Indian e-commerce shopping notifications in standard NotifyIQ format.
    Covers:
    - Amazon India (10): Price drops, orders, lightning deals, coupons, wishlist alerts
    - Flipkart (8): Big Billion Days, SuperCoins, price comparisons, delivery updates
    - Myntra (5): Fashion sales, brand days, coupons
    - Swiggy/Zomato (5): Food order discounts, coupons (SWIGGY50, ZOMATO40), free delivery
    - Paytm/PhonePe (5): Cashback, payment receipts, bill reminders with deadlines
    - Other apps (7): Ajio, Nykaa, Meesho promotional & transactional deals
    """
    return [dict(item) for item in SHOPPING_NOTIFICATIONS_DATA]


def generate_dataset(
    num_samples: int = 400,
    seed: int = 42,
    reference_dt: datetime = datetime(2026, 10, 19, 14, 0, 0, tzinfo=timezone.utc),
    include_shopping: bool = False,
) -> list[dict[str, Any]]:
    """
    Generates a reproducible list of notification dictionaries with ground truth.
    When include_shopping is True, also draws from Indian e-commerce shopping templates.
    """
    random.seed(seed)
    dataset = []

    # Distribute samples across categories
    weights = {
        "action_required": 0.25,
        "transactional": 0.25,
        "social": 0.20,
        "promotional": 0.15,
        "system": 0.10,
        "unknown": 0.05,
    }

    event_counter = 1

    # Base templates or blended with shopping templates
    active_templates = {}
    for cat in CATEGORIES:
        active_templates[cat] = list(TEMPLATES[cat])
        if include_shopping and cat in SHOPPING_TEMPLATES:
            active_templates[cat].extend(SHOPPING_TEMPLATES[cat])

    # Generate exact and near duplicate pairs intentionally for testing
    duplicate_stems = [
        ("com.bank.secure", "Transaction Alert", "Debited USD 12.00 at Metro Transit on 19-Oct."),
        ("com.shopping.mega", "MEGA SALE 50% OFF", "Flash sale ends midnight! Use code SAVE50 on fashion!"),
        ("com.slack", "Daily Standup Reminder", "Please post your standup updates in #engineering."),
    ]

    for category, weight in weights.items():
        cat_count = int(num_samples * weight)
        templates = active_templates[category]

        for _ in range(cat_count):
            pkg, title, body = random.choice(templates)

            # Add synthetic variations (timestamp jitter within past 72 hours)
            time_offset_hours = random.uniform(0.1, 72.0)
            received_dt = reference_dt - timedelta(hours=time_offset_hours)
            received_at_iso = received_dt.isoformat()

            # Ground truth attributes
            has_action = category == "action_required" or (category == "transactional" and "verify" in body.lower())
            has_deadline = any(
                kw in body.lower()
                for kw in ["by ", "before ", "due ", "tomorrow", "tonight", "within ", "expires in", "at ", "ends in"]
            )

            if category == "action_required" and has_deadline:
                gt_priority = "high"
            elif category in ["action_required", "transactional", "system"]:
                gt_priority = "medium"
            elif category == "promotional":
                gt_priority = "low"
            else:
                gt_priority = "medium" if "urgent" in body.lower() else "low"

            event_id = f"evt-syn-{seed}-{event_counter:04d}"
            event_counter += 1

            dataset.append({
                "schema_version": 1,
                "event_id": event_id,
                "package_name": pkg,
                "title": title,
                "text": body,
                "posted_at": received_at_iso,
                "event_type": "posted",
                "ground_truth_category": category,
                "ground_truth_has_action": has_action,
                "ground_truth_has_deadline": has_deadline,
                "ground_truth_priority": gt_priority,
            })

    # Add exact duplicates
    for pkg, title, body in duplicate_stems:
        base_time = (reference_dt - timedelta(hours=2)).isoformat()
        for i in range(2):
            dataset.append({
                "schema_version": 1,
                "event_id": f"evt-dup-{i}-{event_counter:04d}",
                "package_name": pkg,
                "title": title,
                "text": body,
                "posted_at": base_time,
                "event_type": "posted",
                "ground_truth_category": "transactional" if "bank" in pkg else ("promotional" if "mega" in title.lower() else "action_required"),
                "ground_truth_has_action": "standup" in title.lower(),
                "ground_truth_has_deadline": "midnight" in body.lower(),
                "ground_truth_priority": "medium",
            })
            event_counter += 1

    # Shuffle deterministically
    random.shuffle(dataset)
    return dataset


def save_datasets(include_shopping_in_train: bool = False):
    """Generates all synthetic datasets including the comprehensive shopping dataset."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Generate Training Dataset (320 samples, seed 42)
    train_data = generate_dataset(num_samples=320, seed=42, include_shopping=include_shopping_in_train)
    train_csv_path = DATA_DIR / "training_notifications.csv"
    with open(train_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(train_data[0].keys()))
        writer.writeheader()
        writer.writerows(train_data)
    print(f"Saved {len(train_data)} training samples to {train_csv_path}")

    # 2. Generate Held-Out Evaluation Dataset (120 samples, seed 99 - completely distinct seed)
    eval_data = generate_dataset(num_samples=120, seed=99, include_shopping=include_shopping_in_train)
    eval_csv_path = DATA_DIR / "evaluation_notifications.csv"
    with open(eval_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(eval_data[0].keys()))
        writer.writeheader()
        writer.writerows(eval_data)
    print(f"Saved {len(eval_data)} evaluation samples to {eval_csv_path}")

    # 3. Generate Android Sample JSON Export (50 clean notification events)
    sample_events = []
    for item in eval_data[:50]:
        sample_events.append({
            "schema_version": item["schema_version"],
            "event_id": item["event_id"],
            "package_name": item["package_name"],
            "title": item["title"],
            "text": item["text"],
            "posted_at": item["posted_at"],
            "event_type": item["event_type"],
        })
    sample_json_path = DATA_DIR / "sample_notifications.json"
    with open(sample_json_path, "w", encoding="utf-8") as f:
        json.dump(sample_events, f, indent=2)
    print(f"Saved {len(sample_events)} sample JSON notifications to {sample_json_path}")

    # 4. Generate Comprehensive Shopping Dataset (40 Indian e-commerce notifications)
    shopping_events = generate_shopping_dataset()
    shopping_json_path = DATA_DIR / "shopping_notifications.json"
    with open(shopping_json_path, "w", encoding="utf-8") as f:
        json.dump(shopping_events, f, indent=2)
    print(f"Saved {len(shopping_events)} shopping notifications to {shopping_json_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic notification datasets for NotifyIQ")
    parser.add_argument(
        "--shopping-only",
        action="store_true",
        help="Generate only the shopping notifications dataset (data/shopping_notifications.json)",
    )
    parser.add_argument(
        "--include-shopping-in-train",
        action="store_true",
        help="Blend shopping templates into the CSV training and evaluation datasets",
    )
    args = parser.parse_args()

    if args.shopping_only:
        shopping_events = generate_shopping_dataset()
        shopping_json_path = DATA_DIR / "shopping_notifications.json"
        with open(shopping_json_path, "w", encoding="utf-8") as f:
            json.dump(shopping_events, f, indent=2)
        print(f"Saved {len(shopping_events)} shopping notifications to {shopping_json_path}")
    else:
        save_datasets(include_shopping_in_train=args.include_shopping_in_train)


if __name__ == "__main__":
    main()
