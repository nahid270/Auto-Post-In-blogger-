import feedparser
import requests
import time
import threading
import json
import re
from flask import Flask
import os

# ================= কনফিগারেশন =================
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"
CHANNEL_ID = "@CineZoneBD1"
RSS_FEED_URL = "https://banglaflix4k.blogspot.com/feeds/posts/default"
CHECK_INTERVAL = 15 

# আপনার টিউটোরিয়াল ভিডিওর লিংক নিচে দিন (YouTube বা Telegram ভিডিও লিংক)
TUTORIAL_VIDEO_LINK = "https://t.me/HowtoDowlnoad/33" 
# ============================================

app = Flask(__name__)
last_posted_link = None

def send_to_telegram(title, link, image_url, tags):
    api_url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    api_url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # === ১. ক্যাপশন ডিজাইন (আপডেট করা হয়েছে) ===
    # tags ভেরিয়েবলটি আপনার ব্লগের Labels গুলো দেখাবে
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"💿 <b>Quality:</b> HD\n" \
              f"🗣 <b>Language/Genre:</b> {tags}\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"👇 <i>Click buttons to watch or download</i>"

    # === ২. বাটন সেটআপ (টিউটোরিয়াল বাটন সহ) ===
    buttons = {
        "inline_keyboard": [
            [
                {"text": "▶️ Watch Online", "url": link},
                {"text": "📥 Download Now", "url": link}
            ],
            [
                # এই নতুন বাটনটি যুক্ত করা হলো
                {"text": "📺 How to Download (Tutorial)", "url": TUTORIAL_VIDEO_LINK}
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
        # ছবি সহ পাঠানোর চেষ্টা
        if image_url and image_url.startswith('http'):
            payload['photo'] = image_url
            r = requests.post(api_url_photo, data=payload)
            
            if r.status_code == 200:
                print(f"✅ Post Sent with Photo: {title}")
                return 

        # ব্যাকআপ (যদি ছবি না যায়)
        payload.pop('photo', None)
        payload['text'] = caption
        r = requests.post(api_url_msg, data=payload)
        if r.status_code == 200:
            print(f"✅ Post Sent (Text Mode): {title}")

    except Exception as e:
        print(f"❌ Error: {e}")

def get_high_quality_image(entry):
    """ব্লগার থেকে হাই কোয়ালিটি ছবি বের করা"""
    try:
        content = entry.content[0].value
        img_match = re.search(r'<img[^>]+src="([^">]+)"', content)
        if img_match:
            return img_match.group(1)
        if 'media_thumbnail' in entry:
            return entry.media_thumbnail[0]['url'].replace('s72-c', 's1600')
    except:
        pass
    return None

def check_feed():
    global last_posted_link
    print("🤖 Bot is active (With Tutorial Button & Dynamic Tags)...")
    
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if feed.entries:
            last_posted_link = feed.entries[0].link
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
                    print(f"🔥 Processing New Movie: {title}")
                    
                    image_url = get_high_quality_image(latest_post)
                    
                    # === নতুন: লজিক ট্যাগ/লেবেল বের করার জন্য ===
                    tags = "Multi Language" # ডিফল্ট যদি কোনো লেবেল না দেন
                    if 'tags' in latest_post:
                        # ব্লগের সব লেবেল কমা দিয়ে সাজাবে (যেমন: Action, Hindi, 2025)
                        tag_list = [t.term for t in latest_post.tags]
                        tags = ", ".join(tag_list)

                    send_to_telegram(title, current_link, image_url, tags)
                    last_posted_link = current_link
                
                elif last_posted_link is None:
                     last_posted_link = current_link

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"❌ Feed Error: {e}")
            time.sleep(15)

@app.route('/')
def home():
    return "✅ Bot with Tutorial Button is Running!"

def run_bot():
    t = threading.Thread(target=check_feed)
    t.start()

if __name__ == "__main__":
    run_bot()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)port
