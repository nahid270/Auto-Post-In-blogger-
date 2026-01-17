import feedparser
import asyncio
import threading
import json
import re
import base64
import os
import time
from bs4 import BeautifulSoup
from flask import Flask
from pyrogram import Client, filters, enums, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= কনফিগারেশন =================
API_ID = 29462738          # <--- আপনার API ID দিন
API_HASH = "297f51aaab99720a09e80273628c3c24"  # <--- আপনার API HASH দিন
BOT_TOKEN = "8156277951:AAFGsp5IhEhxK8ll2jqBBZQsjqk4hxjkPCQ"

DATA_FILE = 'user_data.json'
CHECK_INTERVAL = 60 
# ============================================

# ক্লায়েন্ট সেটআপ
bot = Client("AutoPostBotMulti", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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

# === হেল্পার ফাংশন ===
def get_language_from_title(title):
    keywords = ["Hindi", "English", "Bengali", "Tamil", "Telugu", "Malayalam", "Dual Audio", "Subtitles", "Hin-Eng"]
    found_langs = []
    for k in keywords:
        if re.search(r'\b' + re.escape(k) + r'\b', title, re.IGNORECASE):
            if k.lower() in ["hin", "hin-eng"]: k = "Hindi-English"
            found_langs.append(k)
    if found_langs: return " + ".join(found_langs)
    match = re.search(r'\[([^0-9]+)\]', title) 
    if match: return match.group(1).strip()
    return None

def parse_html_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {'poster': None, 'download_link': None, 'genre': 'Movie / Web Series', 'language': 'Dual Audio [Hin-Eng]'}
    try:
        img_tag = soup.find('img', class_='poster-img')
        if img_tag: data['poster'] = img_tag.get('src')
        
        btn = soup.find('button', class_='rgb-btn')
        if btn and 'onclick' in btn.attrs:
            match = re.search(r"secureLink\(this,\s*'([^']+)'", btn['onclick'])
            if match: data['download_link'] = base64.b64decode(match.group(1)).decode('utf-8')

        full_text = soup.get_text()
        genre_match = re.search(r'(?:Genre|Category)\s*[:|-]\s*(.*)', full_text, re.IGNORECASE)
        if genre_match: data['genre'] = genre_match.group(1).split('\n')[0].strip()

        lang_match = re.search(r'(?:Language|Audio)\s*[:|-]\s*(.*)', full_text, re.IGNORECASE)
        if lang_match: data['language'] = lang_match.group(1).split('\n')[0].strip()
    except Exception as e:
        pass
    return data

# ================== কমান্ড হ্যান্ডলার ==================

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    welcome_msg = (
        "👋 <b>Welcome to Multi-Channel Auto Post Bot!</b>\n\n"
        "➕ <b>নতুন সেটআপ:</b>\n"
        "<code>/setup @ChannelUsername FeedLink TutorialLink</code>\n\n"
        "📋 <b>লিস্ট দেখতে:</b> /status\n"
        "🗑 <b>ডিলিট করতে:</b> /remove 1"
    )
    await message.reply_text(welcome_msg, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("setup"))
async def setup_command(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    
    if len(parts) >= 3:
        channel = parts[1]
        feed = parts[2]
        tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
        
        new_entry = {"channel": channel, "feed": feed, "tutorial": tutorial, "last_link": None}
        if chat_id not in users_db: users_db[chat_id] = []
        users_db[chat_id].append(new_entry)
        save_data()
        await message.reply_text(f"✅ <b>Connection Added!</b>\n📢 {channel}")
    else:
        await message.reply_text("❌ Format: `/setup @Channel FeedLink TutorialLink`")

@bot.on_message(filters.command("status"))
async def status_command(client, message):
    chat_id = str(message.chat.id)
    user_setups = users_db.get(chat_id, [])
    if not user_setups:
        await message.reply_text("❌ No setups found.")
        return
    msg = "📊 <b>Channels:</b>\n\n"
    for index, setup in enumerate(user_setups):
        msg += f"<b>{index + 1}.</b> 📢 {setup['channel']}\n   🔗 {setup['feed']}\n"
    msg += "\n🗑 Delete: `/remove 1`"
    await message.reply_text(msg, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("remove"))
async def remove_command(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        index = int(parts[1]) - 1
        user_setups = users_db.get(chat_id, [])
        if 0 <= index < len(user_setups):
            removed = user_setups.pop(index)
            save_data()
            await message.reply_text(f"🗑 Deleted: {removed['channel']}")
        else:
            await message.reply_text("❌ Invalid number.")
    else:
        await message.reply_text("❌ Usage: `/remove 1`")

# ================== পোস্ট সেন্ডার ==================
async def send_post_async(chat_id, setup, title, blog_link, html_content):
    extracted = parse_html_data(html_content)
    final_link = extracted['download_link'] if extracted['download_link'] else blog_link
    poster = extracted['poster']
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Now", url=final_link)],
        [InlineKeyboardButton("📺 How to Download", url=setup.get('tutorial', 'https://t.me/'))],
        [InlineKeyboardButton("♻️ Share with Friends", url=f"https://t.me/share/url?url={final_link}")]
    ])

    caption = (
        f"🎬 <b>{title}</b>\n\n"
        f"🎭 <b>Genre:</b> {extracted['genre']}\n"
        f"🔊 <b>Language:</b> {get_language_from_title(title) or extracted['language']}\n"
        f"💿 <b>Quality:</b> <code>HD-Rip | WEB-DL</code>\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"📥 <b>Direct Fast Download Link</b>\n"
        f"👇 <i>Click the button below</i>"
    )

    try:
        target_channel = setup['channel']
        if poster:
            await bot.send_photo(target_channel, poster, caption=caption, reply_markup=keyboard)
        else:
            await bot.send_message(target_channel, caption, reply_markup=keyboard)
        print(f"✅ Sent to {target_channel}: {title}")
    except Exception as e:
        print(f"❌ Error sending to {target_channel}: {e}")

# ================== ফিড চেকার লুপ (FIXED) ==================
def feed_checker():
    load_data()
    print("🔄 Multi-Feed Checker Started...")
    
    # ⚠️ আগে এখানে "with bot:" ছিল, যা ২য় বার বট স্টার্ট করত। এখন নেই।
    while True:
        try:
            for user_id, setups in list(users_db.items()):
                for setup in setups:
                    try:
                        feed = feedparser.parse(setup['feed'])
                        if feed.entries:
                            post = feed.entries[0]
                            link = post.link
                            
                            if setup.get('last_link') != link:
                                content = post.content[0].value if 'content' in post else post.summary
                                
                                # বট অলরেডি স্টার্ট আছে, তাই সরাসরি লুপ ব্যবহার করা হচ্ছে
                                bot.loop.run_until_complete(
                                    send_post_async(user_id, setup, post.title, link, content)
                                )
                                
                                setup['last_link'] = link
                                save_data()
                    except Exception as e:
                        print(f"Feed Error: {e}")
                        
        except Exception as e:
            print(f"Main Loop Error: {e}")
        time.sleep(CHECK_INTERVAL)

# ================== মেইন রানার (FIXED) ==================
if __name__ == "__main__":
    # ১. আগে বট স্টার্ট হবে (ম্যানুয়ালি)
    print("⚡️ Starting Bot Client...")
    bot.start()

    # ২. তারপর থ্রেডগুলো চালু হবে
    threading.Thread(target=feed_checker, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    
    # ৩. বট যাতে বন্ধ না হয়, তাই idle()
    print("✅ Bot is Online & Running...")
    idle()
    
    # ৪. বন্ধ করার সময়
    bot.stop()
