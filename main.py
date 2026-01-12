import feedparser
import requests
import time
import threading
import json
import re
import base64
from bs4 import BeautifulSoup
from flask import Flask
import os

# ================= কনফিগারেশন =================
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"
DATA_FILE = 'user_data.json'
CHECK_INTERVAL = 60 
# ============================================

app = Flask(__name__)
users_db = {}

# === ডাটা লোড/সেভ ===
def load_data():
    global users_db
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                users_db = json.load(f)
    except:
        users_db = {}

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_db, f)
    except:
        pass

# === HTML থেকে সব ডাটা (Link, Poster, Genre, Language) বের করার ফাংশন ===
def parse_html_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # ডিফল্ট ডাটা
    data = {
        'poster': None,
        'download_link': None,
        'genre': 'Movie / Web Series', # ডিফল্ট যদি না পায়
        'language': 'Dual Audio [Hin-Eng]' # ডিফল্ট যদি না পায়
    }
    
    try:
        # ১. পোস্টার বের করা
        img_tag = soup.find('img', class_='poster-img')
        if img_tag:
            data['poster'] = img_tag.get('src')
            
        # ২. সিক্রেট ডাউনলোড লিংক বের করা
        btn = soup.find('button', class_='rgb-btn')
        if btn and 'onclick' in btn.attrs:
            match = re.search(r"secureLink\(this,\s*'([^']+)'", btn['onclick'])
            if match:
                data['download_link'] = base64.b64decode(match.group(1)).decode('utf-8')

        # ৩. Genre এবং Language বের করা (HTML টেক্সট থেকে)
        # আপনার HTML এ যদি লেখা থাকে "Genre: Action" বা "Language: Hindi" তাহলে এটা কাজ করবে
        full_text = soup.get_text()
        
        # Regex দিয়ে খোঁজা হচ্ছে
        genre_match = re.search(r'(?:Genre|Category)\s*[:|-]\s*(.*)', full_text, re.IGNORECASE)
        lang_match = re.search(r'(?:Language|Audio)\s*[:|-]\s*(.*)', full_text, re.IGNORECASE)
        
        if genre_match:
            # অতিরিক্ত স্পেস বা লাইন ব্রেক থাকলে পরিষ্কার করা
            clean_genre = genre_match.group(1).split('\n')[0].strip()
            data['genre'] = clean_genre
            
        if lang_match:
            clean_lang = lang_match.group(1).split('\n')[0].strip()
            data['language'] = clean_lang
            
    except Exception as e:
        print(f"HTML Parsing Error: {e}")
        
    return data

# === টেলিগ্রাম কমান্ড হ্যান্ডলার ===
def handle_commands():
    offset = 0
    print("🎧 Bot Started...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=10"
            r = requests.get(url).json()
            if "result" in r:
                for u in r["result"]:
                    offset = u["update_id"] + 1
                    if "message" in u and "text" in u["message"]:
                        chat_id = str(u["message"]["chat"]["id"])
                        text = u["message"]["text"]
                        
                        if text.startswith("/setup"):
                            parts = text.split()
                            if len(parts) >= 3:
                                channel = parts[1]
                                feed = parts[2]
                                tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
                                users_db[chat_id] = {"channel": channel, "feed": feed, "tutorial": tutorial, "last_link": None}
                                save_data()
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                              data={'chat_id': chat_id, 'text': "✅ Setup Done!"})
        except:
            time.sleep(5)

# === পোস্ট পাঠানোর ফাংশন ===
def send_to_telegram(user_id, title, blog_link, html_content):
    user_config = users_db.get(user_id)
    if not user_config: return

    # HTML থেকে সব ডাটা নেওয়া হচ্ছে
    extracted = parse_html_data(html_content)
    
    final_link = extracted['download_link'] if extracted['download_link'] else blog_link
    poster = extracted['poster']
    genre_text = extracted['genre']
    lang_text = extracted['language']

    # 🔥 ফাইনাল ক্যাপশন 🔥
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"🎭 <b>Genre:</b> {genre_text}\n" \
              f"🔊 <b>Language:</b> {lang_text}\n" \
              f"💿 <b>Quality:</b> <code>HD-Rip | WEB-DL</code>\n" \
              f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n" \
              f"📥 <b>Direct Fast Download Link</b>\n" \
              f"👇 <i>Click the button below</i>"

    buttons = {
        "inline_keyboard": [
            [
                {"text": "📥 Download Now", "url": final_link},
                {"text": "▶️ Watch Online", "url": final_link}
            ],
            [
                {"text": "📸 View Screenshots", "url": blog_link}
            ],
            [
                {"text": "♻️ Share with Friends", "url": f"https://t.me/share/url?url={final_link}"}
            ]
        ]
    }

    payload = {
        'chat_id': user_config['channel'],
        'caption': caption,
        'parse_mode': 'HTML',
        'reply_markup': json.dumps(buttons)
    }

    try:
        if poster:
            payload['photo'] = poster
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=payload)
        else:
            payload['text'] = caption
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=payload)
        print(f"✅ Sent: {title}")
    except Exception as e:
        print(f"❌ Error: {e}")

# === মেইন লুপ ===
def check_feeds_loop():
    load_data()
    while True:
        try:
            for user_id, config in list(users_db.items()):
                feed = feedparser.parse(config['feed'])
                if feed.entries:
                    post = feed.entries[0]
                    link = post.link
                    
                    if config['last_link'] != link:
                        content = post.content[0].value if 'content' in post else post.summary
                        
                        # আমরা এখন আর tags পাঠাচ্ছি না, কারণ সব HTML থেকেই নিবো
                        send_to_telegram(user_id, post.title, link, content)
                        
                        users_db[user_id]['last_link'] = link
                        save_data()
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)

def run_bot():
    t1 = threading.Thread(target=check_feeds_loop)
    t2 = threading.Thread(target=handle_commands)
    t1.start()
    t2.start()

if __name__ == "__main__":
    run_bot()
    app.run(host='0.0.0.0', port=5000)
