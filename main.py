import feedparser
import requests
import time
import threading
import json
from flask import Flask
import os

# ================= কনফিগারেশন =================
# আপনার দেওয়া তথ্য এখানে বসানো হয়েছে
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"
CHANNEL_ID = "@CineZoneBD1"
RSS_FEED_URL = "https://banglaflix4k.blogspot.com/feeds/posts/default"
CHECK_INTERVAL = 15 
# ============================================

app = Flask(__name__)
last_posted_link = None

def send_to_telegram(title, link, image_url):
    # API URL
    api_url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    api_url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # ১. ক্যাপশন ডিজাইন
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"✨ <i>New Movie Uploaded!</i>\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"🍿 <b>Quality:</b> 4K/1080p Web-DL\n" \
              f"🔊 <b>Audio:</b> Dual Audio / Bangla\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"👇 <i>Click the buttons below to watch</i>"

    # ২. বাটন সেটআপ (Error Handling সহ)
    if not link.startswith('http'):
        link = "https://banglaflix4k.blogspot.com" # সেফটি লিংক
        
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

    # ৩. ডাটা পাঠানো (Payload)
    payload = {
        'chat_id': CHANNEL_ID,
        'caption': caption,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps(buttons)
    }

    try:
        # প্রথমে ছবি সহ পাঠানোর চেষ্টা
        if image_url:
            payload['photo'] = image_url
            r = requests.post(api_url_photo, data=payload)
        else:
            # ছবি না থাকলে সরাসরি টেক্সট মোডে যাবে
            r = requests.post(api_url_msg, data=payload)

        # ৪. রেজাল্ট চেক করা
        if r.status_code == 200:
            print(f"✅ SUCCESS: Post sent for '{title}'")
        else:
            print(f"⚠️ Telegram Error: {r.text}")
            # যদি ছবি বা ক্যাপশনের কারণে এরর খায়, তবে সিম্পল টেক্সট পাঠাবে (ব্যাকআপ)
            if "description" in r.text:
                print("🔄 Trying fallback mode (Simple Text)...")
                requests.post(api_url_msg, data={
                    'chat_id': CHANNEL_ID, 
                    'text': f"🎬 {title}\n\nLink: {link}"
                })

    except Exception as e:
        print(f"❌ Network Error: {e}")

def check_feed():
    global last_posted_link
    print("🤖 Bot is active and watching for NEW movies...")
    
    # বট যখন চালু হবে, তখন ব্লগের লাস্ট পোস্টটা দেখে রাখবে (কিন্তু পোস্ট করবে না)
    # যাতে রিস্টার্ট হওয়ার সাথে সাথে পুরনো পোস্ট আবার না যায়।
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if feed.entries:
            last_posted_link = feed.entries[0].link
            print(f"👁️ First Check Done. Ignoring old post: {feed.entries[0].title}")
    except:
        pass

    while True:
        try:
            feed = feedparser.parse(RSS_FEED_URL)
            if feed.entries:
                latest_post = feed.entries[0]
                current_link = latest_post.link
                title = latest_post.title
                
                # লজিক: যদি মেমোরিতে থাকা লিংকের সাথে বর্তমান লিংক না মিলে, তার মানে নতুন পোস্ট এসেছে
                if last_posted_link and current_link != last_posted_link:
                    print(f"🔥 New Movie Detected: {title}")
                    
                    # হাই কোয়ালিটি ইমেজ বের করা
                    image_url = ""
                    if 'media_thumbnail' in latest_post:
                        image_url = latest_post.media_thumbnail[0]['url'].replace('s72-c', 's1600') 
                    
                    send_to_telegram(title, current_link, image_url)
                    
                    # মেমোরি আপডেট
                    last_posted_link = current_link
                
                # যদি সার্ভার প্রথমবার রান হয়
                elif last_posted_link is None:
                     last_posted_link = current_link

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"❌ Feed Check Error: {e}")
            time.sleep(15)

@app.route('/')
def home():
    return "✅ Final Movie Bot is Running Perfectly!"

def run_bot():
    t = threading.Thread(target=check_feed)
    t.start()

if __name__ == "__main__":
    run_bot()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
