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
BOT_TOKEN = "8445524502:AAEhI47vqsJprqt-DViJEPmaEjZJWIwvVjk"
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

# === টাইটেল থেকে ল্যাঙ্গুয়েজ বের করার ফাংশন ===
def get_language_from_title(title):
    keywords = [
        "Hindi", "English", "Bengali", "Tamil", "Telugu", 
        "Malayalam", "Kannada", "Dual Audio", "Multi Audio", 
        "Subtitles", "Hin-Eng", "Hin", "Eng"
    ]
    
    found_langs = []
    
    for k in keywords:
        if re.search(r'\b' + re.escape(k) + r'\b', title, re.IGNORECASE):
            if k.lower() in ["hin", "hin-eng"]: 
                k = "Hindi-English"
            found_langs.append(k)

    if found_langs:
        return " + ".join(found_langs)
    
    match = re.search(r'\[([^0-9]+)\]', title) 
    if match:
        return match.group(1).strip()
        
    return None

# === HTML থেকে ডাটা বের করার ফাংশন ===
def parse_html_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    data = {
        'poster': None,
        'download_link': None,
        'genre': 'Movie / Web Series', 
        'language': 'Dual Audio [Hin-Eng]'
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

        # ৩. Genre বের করা
        full_text = soup.get_text()
        genre_match = re.search(r'(?:Genre|Category)\s*[:|-]\s*(.*)', full_text, re.IGNORECASE)
        
        if genre_match:
            data['genre'] = genre_match.group(1).split('\n')[0].strip()

        lang_match = re.search(r'(?:Language|Audio)\s*[:|-]\s*(.*)', full_text, re.IGNORECASE)
        if lang_match:
            data['language'] = lang_match.group(1).split('\n')[0].strip()
            
    except Exception as e:
        print(f"HTML Parsing Error: {e}")
        
    return data

# === টেলিগ্রাম কমান্ড হ্যান্ডলার (আপডেট করা হয়েছে) ===
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
                        
                        # --- ১. START কমান্ড ---
                        if text == "/start":
                            welcome_msg = (
                                "👋 <b>Welcome to Auto Post Bot!</b>\n\n"
                                "আমি আপনার ব্লগার ওয়েবসাইট থেকে নতুন পোস্ট অটোমেটিক টেলিগ্রাম চ্যানেলে সেন্ড করি।\n\n"
                                "⚙️ <b>কিভাবে সেটআপ করবেন?</b>\n"
                                "নিচের ফরম্যাটে কমান্ড দিন:\n"
                                "<code>/setup @ChannelUsername FeedLink TutorialLink</code>\n\n"
                                "উদাহরণ:\n"
                                "<code>/setup @MyMovieChannel https://site.com/feeds/posts/default https://t.me/tutorial</code>\n\n"
                                "📊 সেটিংস চেক করতে: /status লিখুন।"
                            )
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': welcome_msg, 'parse_mode': 'HTML'})

                        # --- ২. STATUS কমান্ড (সেটিংস দেখার জন্য) ---
                        elif text == "/status":
                            user_data = users_db.get(chat_id)
                            if user_data:
                                status_msg = (
                                    "📊 <b>আপনার বর্তমান সেটিংস:</b>\n\n"
                                    f"📢 <b>চ্যানেল:</b> {user_data['channel']}\n"
                                    f"🔗 <b>ফিড লিংক:</b> {user_data['feed']}\n"
                                    f"📺 <b>টিউটোরিয়াল:</b> {user_data['tutorial']}\n"
                                    f"🔄 <b>লাস্ট পোস্ট লিংক:</b> {user_data.get('last_link', 'None')}"
                                )
                            else:
                                status_msg = "❌ আপনার কোনো সেটআপ পাওয়া যায়নি। দয়া করে আগে /setup কমান্ড ব্যবহার করুন।"
                            
                            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                          data={'chat_id': chat_id, 'text': status_msg, 'parse_mode': 'HTML'})

                        # --- ৩. SETUP কমান্ড ---
                        elif text.startswith("/setup"):
                            parts = text.split()
                            if len(parts) >= 3:
                                channel = parts[1]
                                feed = parts[2]
                                # টিউটোরিয়াল লিংক এখানে সেট হচ্ছে
                                tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
                                users_db[chat_id] = {"channel": channel, "feed": feed, "tutorial": tutorial, "last_link": None}
                                save_data()
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                              data={'chat_id': chat_id, 'text': "✅ <b>Setup Successful!</b>\nএখন থেকে নতুন পোস্ট অটোমেটিক চ্যানেলে যাবে।", 'parse_mode': 'HTML'})
                            else:
                                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                                              data={'chat_id': chat_id, 'text': "❌ ভুল ফরম্যাট! সঠিক ফরম্যাট:\n<code>/setup @Channel FeedLink TutorialLink</code>", 'parse_mode': 'HTML'})
        except Exception as e:
            print(f"Command Error: {e}")
            time.sleep(5)

# === পোস্ট পাঠানোর ফাংশন ===
def send_to_telegram(user_id, title, blog_link, html_content):
    user_config = users_db.get(user_id)
    if not user_config: return

    # HTML থেকে ডাটা নেওয়া
    extracted = parse_html_data(html_content)
    
    final_link = extracted['download_link'] if extracted['download_link'] else blog_link
    poster = extracted['poster']
    genre_text = extracted['genre']
    
    # টিউটোরিয়াল লিংক ডাটাবেস থেকে নেওয়া
    tutorial_link = user_config.get('tutorial', 'https://t.me/')
    
    # ল্যাঙ্গুয়েজ লজিক
    title_lang = get_language_from_title(title)
    if title_lang:
        lang_text = title_lang
    else:
        lang_text = extracted['language']

    # ক্যাপশন
    caption = f"🎬 <b>{title}</b>\n\n" \
              f"🎭 <b>Genre:</b> {genre_text}\n" \
              f"🔊 <b>Language:</b> {lang_text}\n" \
              f"💿 <b>Quality:</b> <code>HD-Rip | WEB-DL</code>\n" \
              f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n" \
              f"📥 <b>Direct Fast Download Link</b>\n" \
              f"👇 <i>Click the button below</i>"

    # বাটন কনফিগারেশন
    buttons = {
        "inline_keyboard": [
            [
                {"text": "📥 Download Now", "url": final_link}
            ],
            [
                {"text": "📺 How to Download", "url": tutorial_link}
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
