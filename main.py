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
CHECK_INTERVAL = 60 
# ============================================

app = Flask(__name__)
bot = Client("AutoPostBotSmart", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
users_db = {} 

# === ওয়েব সার্ভারের রুট (হেলথ চেক) ===
@app.route('/')
def health_check():
    return "Bot is Running! Status: 200 OK"

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

def get_language_from_title(title):
    keywords = ["Hindi", "English", "Bengali", "Tamil", "Telugu", "Dual Audio", "Hin-Eng"]
    found_langs = []
    for k in keywords:
        if re.search(r'\b' + re.escape(k) + r'\b', title, re.IGNORECASE):
            if k.lower() in ["hin", "hin-eng"]: k = "Hindi-English"
            found_langs.append(k)
    if found_langs: return " + ".join(found_langs)
    return "Not Specified"

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
    except Exception:
        pass
    return data

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("👋 <b>Bot is Online!</b>")

@bot.on_message(filters.command("setup"))
async def setup_command(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    if len(parts) >= 3:
        channel, feed = parts[1], parts[2]
        tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
        new_entry = {"channel": channel, "feed": feed, "tutorial": tutorial, "last_ids": []}
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
    msg = "📊 <b>Active Feeds:</b>\n"
    for i, s in enumerate(user_setups):
        msg += f"{i+1}. {s['channel']}\n"
    await message.reply_text(msg, parse_mode=enums.ParseMode.HTML)

# === ম্যানুয়াল পোস্ট ===
@bot.on_message(filters.command("send") & filters.user(users_db.keys()))
async def manual_post(client, message):
    try:
        parts = message.text.split(" ", 2)
        if len(parts) < 2:
            await message.reply("❌ Use: `/send @Channel message`")
            return
        target = parts[1]
        if message.reply_to_message:
            await message.reply_to_message.copy(target)
            await message.reply(f"✅ Copied to {target}")
        elif len(parts) == 3:
            await bot.send_message(target, parts[2])
            await message.reply(f"✅ Sent to {target}")
    except Exception as e:
        await message.reply(f"Error: {e}")

async def send_post_async(setup, title, blog_link, html_content):
    extracted = parse_html_data(html_content)
    final_link = extracted['download_link'] if extracted['download_link'] else blog_link
    poster = extracted['poster']
    tutorial_link = setup.get('tutorial', 'https://t.me/')
    
    post_type = get_post_type(title)
    if post_type == "MOVIE":
        caption = (f"🎬 <b>{title}</b>\n\n🎭 <b>Genre:</b> {extracted['genre']}\n"
                   f"🔊 <b>Language:</b> {get_language_from_title(title) or extracted['language']}\n"
                   f"💿 <b>Quality:</b> <code>HD-Rip | WEB-DL</code>\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
                   f"📥 <b>Direct Fast Download Link</b>\n👇 <i>Click the button below</i>")
    else:
        caption = (f"🔥 <b>{title}</b>\n\n👀 <i>Check out this latest update!</i>\n"
                   f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n👇 <i>Click below to view</i>")

    buttons = [[InlineKeyboardButton("📥 Download / View", url=final_link)],
               [InlineKeyboardButton("📺 How to Download", url=tutorial_link)],
               [InlineKeyboardButton("♻️ Share", url=f"https://t.me/share/url?url={final_link}")]]
    
    try:
        if poster: await bot.send_photo(setup['channel'], poster, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        else: await bot.send_message(setup['channel'], caption, reply_markup=InlineKeyboardMarkup(buttons))
        return True
    except Exception as e:
        print(f"Error sending post: {e}")
        return False

async def checker_loop():
    print("🔄 Checker Loop Started...")
    load_data()
    while True:
        try:
            for user_id, setups in list(users_db.items()):
                for setup in setups:
                    try:
                        feed = feedparser.parse(setup['feed'])
                        if not feed.entries: continue
                        recent = feed.entries[:5][::-1]
                        if 'last_ids' not in setup: setup['last_ids'] = []
                        
                        for post in recent:
                            clean_link = post.link.split('?')[0]
                            uid = post.id if 'id' in post else clean_link
                            if uid not in setup['last_ids']:
                                print(f"✨ New: {post.title}")
                                content = post.content[0].value if 'content' in post else post.summary
                                if await send_post_async(setup, post.title, post.link, content):
                                    setup['last_ids'].append(uid)
                                    if len(setup['last_ids']) > 20: setup['last_ids'].pop(0)
                                    save_data()
                                    await asyncio.sleep(2)
                    except Exception as e:
                        print(f"Feed Err: {e}")
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Loop Err: {e}")
            await asyncio.sleep(10)

async def main():
    await bot.start()
    print("⚡️ Bot Started!")
    asyncio.create_task(checker_loop())
    await idle()
    await bot.stop()

# ==========================================
# IMPORTANT: This handles both Flask & Bot
# ==========================================
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Flask কে আলাদা থ্রেডে রান করা হচ্ছে
    threading.Thread(target=run_flask, daemon=True).start()
    # Bot কে মেইন থ্রেডে রান করা হচ্ছে
    bot.run(main())
