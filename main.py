import feedparser
import requests
import time
import threading
import json
import re
from flask import Flask
import os

# ================= কনফিগারেশন =================
# আপনার বটের টোকেন (এটি ফিক্সড থাকবে)
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"

# ডাটা সেভ রাখার ফাইল
DATA_FILE = 'user_data.json'
CHECK_INTERVAL = 60 # মাল্টি ইউজার তাই ১৫ সেকেন্ড না দিয়ে ১ মিনিট দেওয়া হলো (সেফটির জন্য)
# ============================================

app = Flask(__name__)
# মেমোরিতে ডাটা রাখার জন্য ডিকশনারি
users_db = {}

# === ডাটা লোড এবং সেভ করার ফাংশন ===
def load_data():
    global users_db
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                users_db = json.load(f)
            print("✅ User Data Loaded Successfully!")
        else:
            users_db = {}
    except Exception as e:
        print(f"⚠️ Error loading data: {e}")

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_db, f)
    except Exception as e:
        print(f"⚠️ Error saving data: {e}")

# === টেলিগ্রাম কমান্ড হ্যান্ডলার (নতুন ইউজার অ্যাড করা) ===
def handle_commands():
    offset = 0
    print("🎧 Bot is listening for /setup commands...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=10"
            response = requests.get(url).json()
            
            if "result" in response:
                for update in response["result"]:
                    offset = update["update_id"] + 1
                    
                    if "message" in update and "text" in update["message"]:
                        chat_id = str(update["message"]["chat"]["id"])
                        text = update["message"]["text"]
                        
                        # কমান্ড ফরম্যাট: /setup @Channel FeedLink TutorialLink
                        if text.startswith("/setup"):
                            parts = text.split()
                            if len(parts) >= 4:
                                channel = parts[1]
                                feed_url = parts[2]
                                tutorial_link = parts[3]
                                
                                # ডাটাবেসে সেভ করা
                                users_db[chat_id] = {
                                    "channel": channel,
                                    "feed": feed_url,
                                    "tutorial": tutorial_link,
                                    "last_link": None
                                }
                                save_data()
                                
                                reply = f"✅ <b>Setup Complete!</b>\n\n" \
                                        f"📢 Channel: {channel}\n" \
                                        f"🔗 Feed: {feed_url}\n" \
                                        f"📺 Tutorial: {tutorial_link}\n\n" \
                                        f"<i>Make sure the bot is an Admin in your channel!</i>"
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                              data={'chat_id': chat_id, 'text': reply, 'parse_mode': 'HTML'})
                            else:
                                error_msg = "❌ <b>Wrong Format!</b>\nUse:\n<code>/setup @Channel FeedLink TutorialLink</code>"
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                              data={'chat_id': chat_id, 'text': error_msg, 'parse_mode': 'HTML'})
                                              
                        elif text.startswith("/start"):
                            welcome = "👋 <b>Welcome!</b>\nTo connect your website, send:\n\n<code>/setup @YourChannel FeedLink TutorialLink</code>"
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': welcome, 'parse_mode': 'HTML'})

            time.sleep(1)
        except Exception as e:
            print(f"Command Error: {e}")
            time.sleep(5)

# === পোস্ট পাঠানোর ফাংশন (ডাইনামিক) ===
def send_to_telegram(user_id, title, link, image_url, tags):
    user_config = users_db.get(user_id)
    if not user_config: return

    channel_id = user_config['channel']
    tutorial_link = user_config['tutorial']
    
    api_url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    api_url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"💿 <b>Quality:</b> HD\n" \
              f"🗣 <b>Language:</b> {tags}\n" \
              f"━━━━━━━━━━━━━━━━━━\n" \
              f"👇 <i>Click buttons to watch or download</i>"

    buttons = {
        "inline_keyboard": [
            [
                {"text": "▶️ Watch Online", "url": link},
                {"text": "📥 Download Now", "url": link}
            ],
            [
                {"text": "📺 How to Download", "url": tutorial_link}
            ],
            [
                {"text": "🚀 Share with Friends", "url": f"https://t.me/share/url?url={link}"}
            ]
        ]
    }

    payload = {
        'chat_id': channel_id,
        'caption': caption,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps(buttons)
    }

    try:
        # ছবি সহ পাঠানো
        if image_url and image_url.startswith('http'):
            payload['photo'] = image_url
            r = requests.post(api_url_photo, data=payload)
            if r.status_code == 200:
                print(f"✅ Sent to {channel_id}: {title}")
                return 

        # ছবি ছাড়া ব্যাকআপ
        payload.pop('photo', None)
        payload['text'] = caption
        requests.post(api_url_msg, data=payload)
        print(f"✅ Sent Text to {channel_id}")

    except Exception as e:
        print(f"❌ Sending Error: {e}")

# === ইমেজ বের করার ফাংশন ===
def get_high_quality_image(entry):
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

# === মেইন চেকিং লুপ (সব ইউজারের জন্য) ===
def check_feeds_loop():
    print("🤖 Multi-User Bot Started...")
    load_data() # প্রথমে সেভ করা ডাটা লোড করবে

    while True:
        try:
            # সব ইউজারের লিস্ট চেক করবে
            # users_db.items() এর কপি নেওয়া হচ্ছে যাতে লুপের সময় এরর না হয়
            for user_id, config in list(users_db.items()):
                feed_url = config['feed']
                last_link = config['last_link']
                
                try:
                    feed = feedparser.parse(feed_url)
                    if feed.entries:
                        latest_post = feed.entries[0]
                        current_link = latest_post.link
                        
                        # যদি নতুন পোস্ট হয়
                        if last_link and current_link != last_link:
                            title = latest_post.title
                            image_url = get_high_quality_image(latest_post)
                            
                            tags = "Multi Language"
                            if 'tags' in latest_post:
                                tags = ", ".join([t.term for t in latest_post.tags])

                            print(f"🔥 New Post for {config['channel']}: {title}")
                            send_to_telegram(user_id, title, current_link, image_url, tags)
                            
                            # ডাটাবেস আপডেট
                            users_db[user_id]['last_link'] = current_link
                            save_data()
                        
                        # প্রথমবার রান হলে শুধু লিংক সেভ করবে, পোস্ট করবে না
                        elif last_link is None:
                            users_db[user_id]['last_link'] = current_link
                            save_data()
                            
                except Exception as feed_err:
                    print(f"Feed Error for {user_id}: {feed_err}")

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Main Loop Error: {e}")
            time.sleep(10)

@app.route('/')
def home():
    return f"✅ Multi-User Bot Running! Active Users: {len(users_db)}"

def run_bot():
    # দুটি আলাদা থ্রেড: একটি কমান্ড শুনবে, আরেকটি ফিড চেক করবে
    t1 = threading.Thread(target=check_feeds_loop)
    t2 = threading.Thread(target=handle_commands)
    t1.start()
    t2.start()

if __name__ == "__main__":
    run_bot()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
