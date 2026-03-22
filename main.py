import feedparser
import asyncio
import threading
import json
import re
import base64
import os
import logging
from bs4 import BeautifulSoup
from flask import Flask
from pyrogram import Client, filters, enums, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= কনফিগারেশন =================
API_ID = 19234664
API_HASH = "29c2f3b3d115cf1b0231d816deb271f5"
BOT_TOKEN = "8550876774:AAH9BC7oguSWhC9h7JfevDc1B4psBkW2jq4"

DATA_FILE = 'bot_config.json'
CHECK_INTERVAL = 30 
# ============================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimpleAutoPost")

app = Flask(__name__)
bot = Client("SimpleAutoPostBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
users_db = {} 

@app.route('/')
def status():
    return "✅ Bot is Running!"

def load_data():
    global users_db
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                users_db = json.load(f)
        else:
            users_db = {}
    except:
        users_db = {}

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users_db, f, indent=4)
    except:
        pass

def clean_url(url):
    return url.split('?')[0].split('#')[0]

# === আপনার নতুন HTML এর জন্য আপডেট করা পার্সার ===
def parse_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    data = {
        'poster': None, 
        'd_link': None, 
        'genre': None,
        'language': None,
        'quality': None,
        'size': None,
        'year': None,
        'rating': None,
        'runtime': None,
        'cast': None,
        'story': None
    }
    
    # ১. ইমেজ বের করা
    img_tag = soup.find('div', class_='info-poster')
    if img_tag and img_tag.find('img'):
        data['poster'] = img_tag.find('img')['src']
    
    # ২. ইনফো টেক্সট থেকে মেটাডেটা বের করা (Rating, Genre, Language, Year)
    info_text = soup.find('div', class_='info-text')
    if info_text:
        lines = info_text.get_text(separator="\n").split('\n')
        for line in lines:
            if 'Rating:' in line: data['rating'] = line.replace('⭐ Rating:', '').strip()
            if 'Genre:' in line: data['genre'] = line.replace('🎭 Genre:', '').strip()
            if 'Language:' in line: data['language'] = line.replace('🗣️ Language:', '').strip()
            if 'Runtime:' in line: data['runtime'] = line.replace('⏱️ Runtime:', '').strip()
            if 'Release:' in line: data['year'] = line.replace('📅 Release:', '').strip()
            if 'Cast:' in line: data['cast'] = line.replace('👥 Cast:', '').strip()

    # ৩. স্টোরিলাইন বের করা
    plot_box = soup.find('div', class_='plot-box')
    if plot_box:
        data['story'] = plot_box.text.strip()
    
    # ৪. প্রথম ডাউনলোড লিংক বের করা (Base64 Decode)
    # আপনার কোডে goToLink('base64_string') এভাবে আছে
    first_btn = soup.find('button', onclick=re.compile(r'goToLink'))
    if first_btn:
        try:
            match = re.search(r"goToLink\('([^']+)'\)", first_btn['onclick'])
            if match:
                data['d_link'] = base64.b64decode(match.group(1)).decode('utf-8')
        except: pass

    return data

# ================== কমান্ডস ==================
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 <b>বট রেডি!</b>\n\nচ্যানেল কানেক্ট করতে:\n`/setup @ChannelUsername FeedLink`")

@bot.on_message(filters.command("setup"))
async def setup(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    
    if len(parts) >= 3:
        channel = parts[1]
        feed_url = parts[2]
        tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
        
        try:
            feed = feedparser.parse(feed_url)
            last_known_id = None
            if feed.entries:
                post = feed.entries[0]
                last_known_id = post.id if 'id' in post else clean_url(post.link)
            
            new_config = {"channel": channel, "feed": feed_url, "tutorial": tutorial, "last_id": last_known_id}
            if chat_id not in users_db: users_db[chat_id] = []
            users_db[chat_id].append(new_config)
            save_data()
            await message.reply_text(f"✅ <b>Setup Done!</b>\nConnected: {channel}")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
    else:
        await message.reply_text("❌ নিয়ম: `/setup @Channel FeedLink [Tutorial]`")

# ================== পোস্ট সেন্ডার ==================
async def send_post(config, entry):
    # টাইটেল ক্লিন করা
    clean_title = re.sub(r'\[.*?\]', '', entry.title).strip()
    
    link = clean_url(entry.link)
    content = entry.content[0].value if 'content' in entry else entry.summary
    
    meta = parse_html(content)
    final_link = meta['d_link'] if meta['d_link'] else link
    
    # ক্যাপশন ডিজাইন
    caption = f"🎬 <b>{clean_title}</b>\n"
    caption += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    if meta['rating']:   caption += f"⭐️ <b>Rating:</b> {meta['rating']}\n"
    if meta['year']:     caption += f"📅 <b>Year:</b> {meta['year']}\n"
    if meta['language']: caption += f"🗣 <b>Audio:</b> {meta['language']}\n"
    if meta['runtime']:  caption += f"⏱ <b>Runtime:</b> {meta['runtime']}\n"
    if meta['genre']:    caption += f"🎭 <b>Genre:</b> {meta['genre']}\n"
    
    if meta['story']:
        # স্টোরিলাইন বড় হলে ছোট করা
        story = meta['story'][:250] + "..." if len(meta['story']) > 250 else meta['story']
        caption += f"\n📖 <b>Storyline:</b> <i>{story}</i>\n"
        
    caption += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    caption += f"📥 <b>Direct Download Link Below</b>\n"

    buttons = [
        [InlineKeyboardButton("🔗 Download Now", url=final_link)],
        [InlineKeyboardButton("📺 How to Download", url=config['tutorial'])]
    ]
    
    try:
        if meta['poster']:
            await bot.send_photo(config['channel'], meta['poster'], caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await bot.send_message(config['channel'], caption, reply_markup=InlineKeyboardMarkup(buttons))
        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

# (বাকি মেইন লুপ অংশ আগের মতোই থাকবে)
async def checker_loop():
    load_data()
    while True:
        try:
            changes = False
            for user_id, configs in users_db.items():
                for config in configs:
                    feed = feedparser.parse(config['feed'])
                    if not feed.entries: continue
                    new_posts = []
                    last_id = config.get('last_id')
                    for entry in feed.entries[:5]:
                        uid = entry.id if 'id' in entry else clean_url(entry.link)
                        if uid == last_id: break
                        new_posts.append((entry, uid))
                    if new_posts:
                        for entry, uid in reversed(new_posts):
                            if await send_post(config, entry):
                                config['last_id'] = uid
                                changes = True
                                await asyncio.sleep(2)
            if changes: save_data()
            await asyncio.sleep(CHECK_INTERVAL)
        except: await asyncio.sleep(10)

async def main():
    await bot.start()
    asyncio.create_task(checker_loop())
    await idle()
    await bot.stop()

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    bot.run(main())
