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
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= কনফিগারেশন =================
# আপনার Rename-bot এর API ID এবং HASH এখানে ব্যবহার করবেন
API_ID = 29462738          # <--- আপনার API ID দিন
API_HASH = "297f51aaab99720a09e80273628c3c24"  # <--- আপনার API HASH দিন
BOT_TOKEN = "8156277951:AAFGsp5IhEhxK8ll2jqBBZQsjqk4hxjkPCQ"

DATA_FILE = 'user_data.json'
CHECK_INTERVAL = 60 
# ============================================

# ক্লায়েন্ট সেটআপ
bot = Client("AutoPostBotMulti", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

app = Flask(__name__)
users_db = {} # গঠন: { "user_id": [ {setup1}, {setup2} ] }

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

# ================== মাল্টিপল সেটআপ হ্যান্ডলার ==================

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    welcome_msg = (
        "👋 <b>Welcome to Multi-Channel Auto Post Bot!</b>\n\n"
        "আমি আলাদা আলাদা ওয়েবসাইট থেকে আলাদা আলাদা চ্যানেলে পোস্ট করতে পারি।\n\n"
        "➕ <b>নতুন সেটআপ যুক্ত করতে:</b>\n"
        "<code>/setup @ChannelUsername FeedLink TutorialLink</code>\n\n"
        "📋 <b>সবগুলো কানেকশন দেখতে:</b>\n"
        "/status\n\n"
        "🗑 <b>কোনো কানেকশন ডিলিট করতে:</b>\n"
        "<code>/remove 1</code> (এখানে 1 হলো স্ট্যাটাস লিস্টের সিরিয়াল নাম্বার)"
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
        
        # নতুন এন্ট্রি তৈরি
        new_entry = {
            "channel": channel,
            "feed": feed,
            "tutorial": tutorial,
            "last_link": None
        }
        
        # লিস্ট চেক করা, না থাকলে বানানো
        if chat_id not in users_db:
            users_db[chat_id] = []
            
        # লিস্টে অ্যাড করা (Append)
        users_db[chat_id].append(new_entry)
        save_data()
        
        await message.reply_text(
            f"✅ <b>New Connection Added!</b>\n\n"
            f"📡 Website: {feed}\n"
            f"📢 Channel: {channel}\n\n"
            f"আরও চ্যানেল অ্যাড করতে চাইলে আবার /setup কমান্ড দিন।"
        )
    else:
        await message.reply_text("❌ ভুল ফরম্যাট! সঠিক ফরম্যাট:\n<code>/setup @Channel FeedLink TutorialLink</code>")

@bot.on_message(filters.command("status"))
async def status_command(client, message):
    chat_id = str(message.chat.id)
    user_setups = users_db.get(chat_id, [])
    
    if not user_setups:
        await message.reply_text("❌ আপনার কোনো সেটআপ নেই।")
        return

    msg = "📊 <b>আপনার কানেক্ট করা চ্যানেলসমূহ:</b>\n\n"
    for index, setup in enumerate(user_setups):
        msg += (
            f"<b>{index + 1}.</b> 📢 {setup['channel']}\n"
            f"   🔗 {setup['feed']}\n"
            f"   ----------------------------\n"
        )
    
    msg += "\n🗑 কোনোটা ডিলিট করতে চাইলে লিখুন: `/remove নাম্বার` (যেমন: `/remove 1`)"
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
            await message.reply_text(f"🗑 <b>Deleted Successfully:</b>\n📢 {removed['channel']}")
        else:
            await message.reply_text("❌ ভুল নাম্বার! /status দিয়ে সঠিক নাম্বার দেখুন।")
    else:
        await message.reply_text("❌ ব্যবহার: `/remove 1`")

# ================== পোস্ট সেন্ডার (লজিক আপডেট) ==================
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
        # এখানে setup['channel'] ব্যবহার করা হচ্ছে, যাতে সঠিক চ্যানেলে যায়
        target_channel = setup['channel']
        if poster:
            await bot.send_photo(target_channel, poster, caption=caption, reply_markup=keyboard)
        else:
            await bot.send_message(target_channel, caption, reply_markup=keyboard)
        print(f"✅ Sent to {target_channel}: {title}")
    except Exception as e:
        print(f"❌ Error sending to {target_channel}: {e}")

# ================== ফিড চেকার লুপ (Multi-Loop) ==================
def feed_checker():
    load_data()
    print("🔄 Multi-Feed Checker Started...")
    with bot:
        while True:
            try:
                # প্রতিটি ইউজার চেক করবে
                for user_id, setups in list(users_db.items()):
                    # প্রতিটি ইউজারের সবকটি সেটআপ চেক করবে
                    for setup in setups:
                        try:
                            feed = feedparser.parse(setup['feed'])
                            if feed.entries:
                                post = feed.entries[0]
                                link = post.link
                                
                                # যদি নতুন লিংক হয়
                                if setup.get('last_link') != link:
                                    content = post.content[0].value if 'content' in post else post.summary
                                    
                                    # পোস্ট পাঠানো
                                    bot.loop.run_until_complete(
                                        send_post_async(user_id, setup, post.title, link, content)
                                    )
                                    
                                    # লিংক আপডেট এবং সেভ
                                    setup['last_link'] = link
                                    save_data()
                        except Exception as e:
                            print(f"Error parsing feed {setup.get('feed')}: {e}")
                            
            except Exception as e:
                print(f"Main Loop Error: {e}")
            time.sleep(CHECK_INTERVAL)

# ================== মেইন রানার ==================
if __name__ == "__main__":
    threading.Thread(target=feed_checker, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    print("⚡️ Multi-Channel Bot Starting...")
    bot.run()
