import feedparser
import requests
import time
import threading
import json
from flask import Flask
import os

# ================= কনফিগারেশন (আপনার তথ্য) =================
# ১. আপনার বটের টোকেন
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"

# ২. আপনার চ্যানেলের ইউজারনেম
CHANNEL_ID = "@CineZoneBD1"

# ৩. আপনার ব্লগের ফিড লিংক
RSS_FEED_URL = "https://banglaflix4k.blogspot.com/feeds/posts/default"

# ৪. চেক করার সময় (১৫ সেকেন্ড)
CHECK_INTERVAL = 15 
# ============================================================

app = Flask(__name__)
last_posted_link = None

def send_to_telegram(title, link, image_url):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    # === ১. প্রিমিয়াম ক্যাপশন ডিজাইন ===
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"✨ <i>New Movie Uploaded!</i>\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"🍿 <b>Quality:</b> 4K/1080p Web-DL\n" \
              f"🔊 <b>Audio:</b> Dual Audio / Bangla\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"👇 <i>Click the buttons below to watch</i>"

    # === ২. ইনলাইন বাটন (Inline Buttons) ===
    buttons = {
        "inline_keyboard": [
            [
                {"text": "▶️ Watch Online", "url": link},
                {"text": "📥 Download Now", "url": link}
            ],
            [
                {"text": "🚀 Share with Friends", "url": f"https://t.me/share/url?url={link}"}
            ]
        ]
    }

    payload = {
        'chat_id': CHANNEL_ID,
        'caption': caption,
        'parse_mode': 'HTML',
        'photo': image_url,
        'reply_markup': json.dumps(buttons) # বাটন যুক্ত করা হলো
    }
    
    try:
        r = requests.post(api_url, data=payload)
        if r.status_code == 200:
            print(f"✅ Premium Post Sent Successfully: {title}")
        else:
            # যদি ছবি সেন্ড করতে সমস্যা হয়, তবে শুধু টেক্সট এবং বাটন পাঠাবে
            api_url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload.pop('photo') # ছবি বাদ দেওয়া হলো
            requests.post(api_url_msg, data=payload)
            print(f"⚠️ Photo failed, sent text mode. Error: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_feed():
    global last_posted_link
    print("Bot started watching for new movies... (Checking every 15 seconds)")
    
    # বট চালু হওয়ার সময় লাস্ট পোস্টটি মনে রাখবে
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if feed.entries:
            last_posted_link = feed.entries[0].link
            print(f"Initial setup done. Last post on site: {feed.entries[0].title}")
    except:
        pass

    while True:
        try:
            feed = feedparser.parse(RSS_FEED_URL)
            if feed.entries:
                latest_post = feed.entries[0]
                current_link = latest_post.link
                
                # নতুন পোস্ট পেলে
                if last_posted_link and current_link != last_posted_link:
                    print(f"New post detected! Processing: {latest_post.title}")
                    
                    title = latest_post.title
                    
                    # হাই-কোয়ালিটি ছবি বের করা
                    image_url = ""
                    if 'media_thumbnail' in latest_post:
                        image_url = latest_post.media_thumbnail[0]['url'].replace('s72-c', 's1600') 
                    
                    send_to_telegram(title, current_link, image_url)
                    
                    # আপডেট করা
                    last_posted_link = current_link
                
                elif last_posted_link is None:
                     last_posted_link = current_link

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error checking feed: {e}")
            time.sleep(15)

# রেন্ডার বা সার্ভারের জন্য রুট
@app.route('/')
def home():
    return "Premium Movie Bot is Running!"

def run_bot():
    t = threading.Thread(target=check_feed)
    t.start()

if __name__ == "__main__":
    run_bot()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
