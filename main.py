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
API_ID = 19234664
API_HASH = "29c2f3b3d115cf1b0231d816deb271f5"
BOT_TOKEN = "8550876774:AAH9BC7oguSWhC9h7JfevDc1B4psBkW2jq4"

DATA_FILE = 'user_data.json'
CHECK_INTERVAL = 60 # চেক করার সময় একটু বাড়ানো হলো সার্ভার লোড কমাতে
# ============================================

app = Flask(__name__)
bot = Client("AutoPostBotSmart", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
users_db = {} 

# === হেলথ চেক (ওয়েবসাইট পিং রাখার জন্য) ===
@app.route('/')
def hello():
    return "Bot is Running Successfully!"

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
            json.dump(users_db, f, indent=4)
    except:
        pass

# === পোস্টের ধরন চেক ===
def get_post_type(title):
    movie_keywords = [
        "480p", "720p", "1080p", "Movie", "Season", "Episode", 
        "Dual Audio", "Web Series", "BluRay", "HDRip", "WEB-DL", 
        "Hindi", "Netflix", "Amazon", "Dubbed"
    ]
    for k in movie_keywords:
        if k.lower() in title.lower():
            return "MOVIE"
    return "GENERAL"

# === ল্যাঙ্গুয়েজ ডিটেকশন ===
def get_language_from_title(title):
    keywords = ["Hindi", "English", "Bengali", "Tamil", "Telugu", "Dual Audio", "Hin-Eng"]
    found_langs = []
    for k in keywords:
        if re.search(r'\b' + re.escape(k) + r'\b', title, re.IGNORECASE):
            if k.lower() in ["hin", "hin-eng"]: k = "Hindi-English"
            found_langs.append(k)
    if found_langs: return " + ".join(found_langs)
    return "N/A"

# === HTML পার্সার ===
def parse_html_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {'poster': None, 'download_link': None, 'genre': 'N/A', 'language': 'N/A'}
    try:
        img_tag = soup.find('img')
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
    except:
        pass
    return data

# ================== কমান্ড হ্যান্ডলার ==================
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("👋 <b>Smart Auto Post Bot!</b>\nএখন ডুপ্লিকেট ফিক্স এবং ম্যানুয়াল পোস্ট ফিচার যুক্ত করা হয়েছে।")

@bot.on_message(filters.command("setup"))
async def setup_command(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    if len(parts) >= 3:
        channel, feed = parts[1], parts[2]
        tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
        
        # এখানে last_ids লিস্ট যুক্ত করা হলো (ডুপ্লিকেট আটকাতে)
        new_entry = {
            "channel": channel, 
            "feed": feed, 
            "tutorial": tutorial, 
            "last_ids": [] 
        }
        
        if chat_id not in users_db: users_db[chat_id] = []
        users_db[chat_id].append(new_entry)
        save_data()
        await message.reply_text(f"✅ Setup Done for {channel}")
    else:
        await message.reply_text("❌ Use: `/setup @Channel FeedLink TutorialLink`")

@bot.on_message(filters.command("status"))
async def status_command(client, message):
    chat_id = str(message.chat.id)
    user_setups = users_db.get(chat_id, [])
    if not user_setups:
        await message.reply_text("❌ No setups found.")
        return
    msg = "📊 <b>Connected Feeds:</b>\n"
    for i, s in enumerate(user_setups):
        msg += f"{i+1}. {s['channel']}\n"
    await message.reply_text(msg, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("remove"))
async def remove_command(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        index = int(parts[1]) - 1
        user_setups = users_db.get(chat_id, [])
        if 0 <= index < len(user_setups):
            user_setups.pop(index)
            save_data()
            await message.reply_text("🗑 Removed.")
        else:
            await message.reply_text("❌ Invalid index.")

# === ম্যানুয়াল পোস্ট কমান্ড ===
@bot.on_message(filters.command("send"))
async def manual_send(client, message):
    # সিকিউরিটি চেক: যে কেউ যাতে পোস্ট করতে না পারে
    if str(message.chat.id) not in users_db:
        return

    try:
        parts = message.text.split(" ", 2)
        if len(parts) < 2:
            await message.reply("❌ Use: `/send @Channel Message`")
            return
        
        target = parts[1]
        
        if message.reply_to_message:
            await message.reply_to_message.copy(target)
            await message.reply(f"✅ Copied to {target}")
        elif len(parts) == 3:
            await bot.send_message(target, parts[2])
            await message.reply(f"✅ Sent to {target}")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# ================== পোস্ট সেন্ডার ফাংশন ==================
async def send_post_async(setup, title, blog_link, html_content):
    extracted = parse_html_data(html_content)
    final_link = extracted['download_link'] if extracted['download_link'] else blog_link
    poster = extracted['poster']
    tutorial_link = setup.get('tutorial', 'https://t.me/') 
    
    post_type = get_post_type(title)

    if post_type == "MOVIE":
        caption = (
            f"🎬 <b>{title}</b>\n\n"
            f"🎭 <b>Genre:</b> {extracted['genre']}\n"
            f"🔊 <b>Language:</b> {get_language_from_title(title) or extracted['language']}\n"
            f"💿 <b>Quality:</b> <code>HD-Rip | WEB-DL</code>\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"📥 <b>Direct Fast Download Link</b>\n"
            f"👇 <i>Click the button below</i>"
        )
        buttons = [
            [InlineKeyboardButton("📥 Download Now", url=final_link)],
            [InlineKeyboardButton("📺 How to Download", url=tutorial_link)],
            [InlineKeyboardButton("♻️ Share", url=f"https://t.me/share/url?url={final_link}")]
        ]

    else:
        caption = (
            f"🔥 <b>{title}</b>\n\n"
            f"👀 <i>Check out this latest update!</i>\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"👇 <i>Click below to view</i>"
        )
        buttons = [
            [InlineKeyboardButton("🔗 View Post / Watch Video", url=final_link)],
            [InlineKeyboardButton("📺 How to Download", url=tutorial_link)], 
            [InlineKeyboardButton("♻️ Share", url=f"https://t.me/share/url?url={final_link}")]
        ]

    keyboard = InlineKeyboardMarkup(buttons)

    try:
        if poster:
            await bot.send_photo(setup['channel'], poster, caption=caption, reply_markup=keyboard)
        else:
            await bot.send_message(setup['channel'], caption, reply_markup=keyboard)
        print(f"✅ Sent: {title}")
        return True
    except Exception as e:
        print(f"❌ Send Error: {e}")
        return False

# ================== মেইন লুপ (Fixed) ==================
async def checker_loop():
    print("🔄 Smart Checker Loop Started...")
    load_data() # শুরুতে একবার ডাটা লোড
    while True:
        try:
            for user_id, setups in list(users_db.items()):
                for setup in setups:
                    try:
                        feed = feedparser.parse(setup['feed'])
                        if feed.entries:
                            # শেষ ৫টি পোস্ট চেক করবে
                            recent_entries = feed.entries[:5]
                            recent_entries.reverse() # পুরাতন থেকে নতুন সিরিয়ালে পোস্ট হবে

                            if 'last_ids' not in setup: setup['last_ids'] = []

                            for post in recent_entries:
                                # Unique ID তৈরি (লিংক থেকে প্যারামিটার বাদ দিয়ে)
                                clean_link = post.link.split('?')[0]
                                unique_id = post.id if 'id' in post else clean_link

                                if unique_id not in setup['last_ids']:
                                    print(f"✨ New Post Found: {post.title}")
                                    content = post.content[0].value if 'content' in post else post.summary
                                    
                                    success = await send_post_async(setup, post.title, post.link, content)
                                    
                                    if success:
                                        setup['last_ids'].append(unique_id)
                                        # ২০ টার বেশি আইডি রাখব না
                                        if len(setup['last_ids']) > 20:
                                            setup['last_ids'].pop(0)
                                        save_data()
                                        await asyncio.sleep(3) # স্প্যাম আটকাতে বিরতি
                    except Exception as e:
                        print(f"Feed Error: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(10)

async def main():
    await bot.start()
    print("⚡️ Smart Bot Started Successfully!")
    asyncio.create_task(checker_loop())
    await idle()
    await bot.stop()

if __name__ == "__main__":
    # Flask আলাদা পোর্টে রান হবে
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    bot.run(main())
