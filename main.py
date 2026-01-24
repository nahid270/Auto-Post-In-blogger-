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
API_ID = 19234664             # <--- আপনার API ID
API_HASH = "29c2f3b3d115cf1b0231d816deb271f5"   # <--- আপনার API HASH
BOT_TOKEN = "8550876774:AAH9BC7oguSWhC9h7JfevDc1B4psBkW2jq4"

DATA_FILE = 'user_data.json'
CHECK_INTERVAL = 20 
# ============================================

app = Flask(__name__)
bot = Client("AutoPostBotSmart", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
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

# === পোস্টের ধরন চেক করার ফাংশন ===
def get_post_type(title):
    # এই শব্দগুলো থাকলে মুভি হিসেবে ধরবে
    movie_keywords = [
        "480p", "720p", "1080p", "Movie", "Season", "Episode", 
        "Dual Audio", "Web Series", "BluRay", "HDRip", "WEB-DL", 
        "Hindi", "Netflix", "Amazon", "Dubbed"
    ]
    
    for k in movie_keywords:
        if k.lower() in title.lower():
            return "MOVIE"
            
    return "GENERAL"

# === হেল্পার ফাংশন ===
def get_language_from_title(title):
    keywords = ["Hindi", "English", "Bengali", "Tamil", "Telugu", "Dual Audio", "Hin-Eng"]
    found_langs = []
    for k in keywords:
        if re.search(r'\b' + re.escape(k) + r'\b', title, re.IGNORECASE):
            if k.lower() in ["hin", "hin-eng"]: k = "Hindi-English"
            found_langs.append(k)
    if found_langs: return " + ".join(found_langs)
    return None

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
    except Exception as e:
        pass
    return data

# ================== কমান্ড হ্যান্ডলার ==================
@bot.on_message(filters.command("start"))
async def start_command(client, message):
    await message.reply_text("👋 <b>Smart Auto Post Bot!</b>\nমুভি এবং ভাইরাল পোস্ট আলাদাভাবে ডিটেক্ট করতে পারে।")

@bot.on_message(filters.command("setup"))
async def setup_command(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    if len(parts) >= 3:
        channel, feed = parts[1], parts[2]
        tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
        new_entry = {"channel": channel, "feed": feed, "tutorial": tutorial, "last_link": None}
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
    msg = "📊 <b>Connected:</b>\n"
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

# ================== পোস্ট সেন্ডার (বাটন ফিক্স করা হয়েছে) ==================
async def send_post_async(setup, title, blog_link, html_content):
    extracted = parse_html_data(html_content)
    final_link = extracted['download_link'] if extracted['download_link'] else blog_link
    poster = extracted['poster']
    tutorial_link = setup.get('tutorial', 'https://t.me/') # টিউটোরিয়াল লিংক
    
    post_type = get_post_type(title)

    if post_type == "MOVIE":
        # === মুভি টেমপ্লেট ===
        caption = (
            f"🎬 <b>{title}</b>\n\n"
            f"🎭 <b>Genre:</b> {extracted['genre']}\n"
            f"🔊 <b>Language:</b> {get_language_from_title(title) or extracted['language']}\n"
            f"💿 <b>Quality:</b> <code>HD-Rip | WEB-DL</code>\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"📥 <b>Direct Fast Download Link</b>\n"
            f"👇 <i>Click the button below</i>"
        )
        # মুভির বাটন (টিউটোরিয়াল সহ)
        buttons = [
            [InlineKeyboardButton("📥 Download Now", url=final_link)],
            [InlineKeyboardButton("📺 How to Download", url=tutorial_link)], # <--- বাটন আছে
            [InlineKeyboardButton("♻️ Share", url=f"https://t.me/share/url?url={final_link}")]
        ]

    else:
        # === সাধারণ/ভাইরাল পোস্ট টেমপ্লেট ===
        caption = (
            f"🔥 <b>{title}</b>\n\n"
            f"👀 <i>Check out this latest update!</i>\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"👇 <i>Click below to view</i>"
        )
        # সাধারণ পোস্টের বাটন (টিউটোরিয়াল সহ - এখানে অ্যাড করা হলো)
        buttons = [
            [InlineKeyboardButton("🔗 View Post / Watch Video", url=final_link)],
            [InlineKeyboardButton("📺 How to Download", url=tutorial_link)], # <--- এই বাটনটি নতুন যুক্ত করা হলো
            [InlineKeyboardButton("♻️ Share", url=f"https://t.me/share/url?url={final_link}")]
        ]

    keyboard = InlineKeyboardMarkup(buttons)

    try:
        if poster:
            await bot.send_photo(setup['channel'], poster, caption=caption, reply_markup=keyboard)
        else:
            await bot.send_message(setup['channel'], caption, reply_markup=keyboard)
        print(f"✅ Sent ({post_type}): {title}")
    except Exception as e:
        print(f"❌ Error: {e}")

# ================== মেইন লুপ ==================
async def checker_loop():
    print("🔄 Smart Checker Loop Started...")
    while True:
        try:
            load_data()
            for user_id, setups in list(users_db.items()):
                for setup in setups:
                    try:
                        feed = feedparser.parse(setup['feed'])
                        if feed.entries:
                            post = feed.entries[0]
                            link = post.link
                            
                            if setup.get('last_link') != link:
                                print(f"✨ New Post: {post.title}")
                                content = post.content[0].value if 'content' in post else post.summary
                                
                                await send_post_async(setup, post.title, link, content)
                                
                                setup['last_link'] = link
                                save_data()
                    except Exception as e:
                        print(f"Feed Error: {e}")
            await asyncio.sleep(CHECK_INTERVAL)
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(10)

async def main():
    await bot.start()
    print("⚡️ Smart Bot Started!")
    asyncio.create_task(checker_loop())
    await idle()
    await bot.stop()

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    bot.run(main())
