import feedparser
import requests
import time
import threading
import json
import re  # ছবি খোঁজার জন্য নতুন টুল
from flask import Flask
import os

# ================= কনফিগারেশন =================
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"
CHANNEL_ID = "@CineZoneBD1"
RSS_FEED_URL = "https://banglaflix4k.blogspot.com/feeds/posts/default"
CHECK_INTERVAL = 15 
# ============================================

app = Flask(__name__)
last_posted_link = None

def send_to_telegram(title, link, image_url):
    api_url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    api_url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # === ১. প্রিমিয়াম ডিজাইন (ক্যাপশন) ===
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"✨ <i>New Movie Uploaded!</i>\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"🍿 <b>Quality:</b> 4K/1080p Web-DL\n" \
              f"🔊 <b>Audio:</b> Dual Audio / Bangla\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"👇 <i>Click the buttons below to watch</i>"

    # === ২. বাটন সেটআপ ===
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
        'reply_markup': json.dumps(buttons)
    }

    try:
        # যদি ছবি পাওয়া যায়, তাহলে ছবি সহ পাঠাবে (সবচেয়ে সুন্দর দেখাবে)
        if image_url and image_url.startswith('http'):
            payload['photo'] = image_url
            r = requests.post(api_url_photo, data=payload)
            
            if r.status_code == 200:
                print(f"✅ Success with Photo: {title}")
                return # কাজ শেষ, ফাংশন থেকে বের হয়ে যাবে
            else:
                print(f"⚠️ Photo Error: {r.text} - Switching to Text Mode with Buttons")

        # === ব্যাকআপ প্ল্যান: যদি ছবি না থাকে বা এরর হয় ===
        # তবুও বাটন সহ সুন্দর টেক্সট পাঠাবে (আগের মতো সাদামাটা লিংক দেখাবে না)
        payload.pop('photo', None) # ফটো ফিল্ড মুছে ফেলা হলো
        payload['text'] = caption # ক্যাপশনকে টেক্সট হিসেবে সেট করা হলো
        payload['disable_web_page_preview'] = False # লিংক প্রিভিউ চালু থাকবে
        
        r = requests.post(api_url_msg, data=payload)
        if r.status_code == 200:
            print(f"✅ Success (Text Mode): {title}")
        else:
            print(f"❌ Critical Error: {r.text}")

    except Exception as e:
        print(f"❌ Network Error: {e}")

def get_high_quality_image(entry):
    """ব্লগার পোস্ট থেকে সেরা ছবিটি খুঁজে বের করার ফাংশন"""
    try:
        # ১. প্রথমে পোস্টের ভেতরের HTML কন্টেন্ট চেক করবে (সবচেয়ে ভালো উপায়)
        content = entry.content[0].value
        img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
        if img_match:
            return img_match.group(1)
            
        # ২. যদি কন্টেন্টে না পায়, থাম্বনেইল চেক করবে
        if 'media_thumbnail' in entry:
            return entry.media_thumbnail[0]['url'].replace('s72-c', 's1600') # হাই কোয়ালিটি কনভার্ট
            
    except Exception as e:
        print(f"Image extract error: {e}")
    return None

def check_feed():
    global last_posted_link
    print("🤖 Bot is active...")
    
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if feed.entries:
            last_posted_link = feed.entries[0].link
            print(f"Initial Check Done. Ignoring: {feed.entries[0].title}")
    except:
        pass

    while True:
        try:
            feed = feedparser.parse(RSS_FEED_URL)
            if feed.entries:
                latest_post = feed.entries[0]
                current_link = latest_post.link
                title = latest_post.title
                
                if last_posted_link and current_link != last_posted_link:
                    print(f"🔥 New Post: {title}")
                    
                    # নতুন এবং শক্তিশালী ইমেজ বের করার পদ্ধতি
                    image_url = get_high_quality_image(latest_post)
                    
                    send_to_telegram(title, current_link, image_url)
                    last_posted_link = current_link
                
                elif last_posted_link is None:
                     last_posted_link = current_link

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"❌ Feed Error: {e}")
            time.sleep(15)

@app.route('/')
def home():
    return "✅ Bot Updated with Image Fixer!"

def run_bot():
    t = threading.Thread(target=check_feed)
    t.start()

if __name__ == "__main__":
    run_bot()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
