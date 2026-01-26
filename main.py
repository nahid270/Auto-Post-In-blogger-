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
CHECK_INTERVAL = 30  # প্রতি ৬০ সেকেন্ডে চেক করবে
# ============================================

# লগিং (ডিবাগিং এর জন্য)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimpleAutoPost")

app = Flask(__name__)
bot = Client("SimpleAutoPostBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
users_db = {} 

# === হেলথ চেক ===
@app.route('/')
def status():
    return "✅ Bot is Running!"

# === ডাটাবেস হ্যান্ডলিং ===
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

# === হেল্পার ফাংশন ===
def clean_url(url):
    # লিংকের শেষে ?m=1 বা #comment থাকলে রিমুভ করে ক্লিন লিংক বানাবে
    return url.split('?')[0].split('#')[0]

def parse_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {'poster': None, 'd_link': None, 'genre': 'N/A'}
    
    img = soup.find('img')
    if img: data['poster'] = img.get('src')
    
    btn = soup.find('button', class_='rgb-btn')
    if btn and 'onclick' in btn.attrs:
        try:
            match = re.search(r"secureLink\(this,\s*'([^']+)'", btn['onclick'])
            if match:
                data['d_link'] = base64.b64decode(match.group(1)).decode('utf-8')
        except: pass
        
    text = soup.get_text()
    g_match = re.search(r'(?:Genre|Category)\s*[:|-]\s*(.*)', text, re.IGNORECASE)
    if g_match: data['genre'] = g_match.group(1).split('\n')[0].strip()
    
    return data

# ================== কমান্ডস ==================
@bot.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 <b>বট রেডি!</b>\n\nচ্যানেল কানেক্ট করতে:\n`/setup @ChannelUsername FeedLink`\n\nনোট: কানেক্ট করার পর <b>নতুন</b> যা পোস্ট করবেন শুধু সেটাই চ্যানেলে যাবে।")

@bot.on_message(filters.command("setup"))
async def setup(client, message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    
    if len(parts) >= 3:
        channel = parts[1]
        feed_url = parts[2]
        tutorial = parts[3] if len(parts) > 3 else "https://t.me/"
        
        try:
            # ১. সেটআপের সময়ই ফিড চেক করে লেটেস্ট পোস্টের আইডি নিয়ে নেওয়া হচ্ছে
            feed = feedparser.parse(feed_url)
            last_known_id = None
            
            if feed.entries:
                # লেটেস্ট পোস্টের ID সেভ করে রাখলাম যাতে এটা আর সেন্ড না করে
                post = feed.entries[0]
                last_known_id = post.id if 'id' in post else clean_url(post.link)
            
            new_config = {
                "channel": channel,
                "feed": feed_url,
                "tutorial": tutorial,
                "last_id": last_known_id # এই আইডি বা এর আগের গুলো আর সেন্ড হবে না
            }
            
            if chat_id not in users_db: users_db[chat_id] = []
            
            # মাল্টিপল চ্যানেল সাপোর্ট: নতুন কনফিগারেশন লিস্টে যোগ করা হলো
            users_db[chat_id].append(new_config)
            save_data()
            
            await message.reply_text(f"✅ <b>Setup Done!</b>\nConnected: {channel}\n\nএখন থেকে ব্লগারে নতুন পোস্ট করলে অটোমেটিক যাবে।")
            
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
    else:
        await message.reply_text("❌ নিয়ম: `/setup @Channel FeedLink [Tutorial]`")

@bot.on_message(filters.command("status"))
async def status_cmd(client, message):
    chat_id = str(message.chat.id)
    if chat_id in users_db and users_db[chat_id]:
        msg = "📋 <b>আপনার কানেক্ট করা চ্যানেলসমূহ:</b>\n"
        for i, conf in enumerate(users_db[chat_id]):
            msg += f"{i+1}. {conf['channel']}\n"
        await message.reply_text(msg)
    else:
        await message.reply_text("❌ কোনো চ্যানেল সেটআপ করা নেই।")

@bot.on_message(filters.command("remove"))
async def remove_cmd(client, message):
    # চ্যানেল রিমুভ করার কমান্ড
    chat_id = str(message.chat.id)
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        idx = int(parts[1]) - 1
        if chat_id in users_db and 0 <= idx < len(users_db[chat_id]):
            removed = users_db[chat_id].pop(idx)
            save_data()
            await message.reply_text(f"🗑 রিমুভ করা হয়েছে: {removed['channel']}")
        else:
            await message.reply_text("❌ ভুল ইনডেক্স। /status চেক করুন।")
    else:
        await message.reply_text("❌ নিয়ম: `/remove 1` (এখানে 1 হলো লিস্ট নাম্বার)")

# ================== পোস্ট সেন্ডার ==================
async def send_post(config, entry):
    title = entry.title
    link = clean_url(entry.link)
    content = entry.content[0].value if 'content' in entry else entry.summary
    
    meta = parse_html(content)
    final_link = meta['d_link'] if meta['d_link'] else link
    
    # ক্যাপশন তৈরি
    caption = (
        f"🔥 <b>{title}</b>\n\n"
        f"🎭 <b>Genre:</b> {meta['genre']}\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"📥 <b>Download / View Post</b>\n"
        f"👇 <i>Click the button below</i>"
    )
    
    buttons = [
        [InlineKeyboardButton("🔗 View / Download", url=final_link)],
        [InlineKeyboardButton("📺 Tutorial", url=config['tutorial'])]
    ]
    
    try:
        if meta['poster']:
            await bot.send_photo(config['channel'], meta['poster'], caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await bot.send_message(config['channel'], caption, reply_markup=InlineKeyboardMarkup(buttons))
        logger.info(f"Sent: {title}")
        return True
    except Exception as e:
        logger.error(f"Failed to send to {config['channel']}: {e}")
        return False

# ================== মেইন লুপ ==================
async def checker_loop():
    logger.info("🔄 Checker Loop Started...")
    load_data()
    
    while True:
        try:
            changes = False
            for user_id, configs in users_db.items():
                for config in configs:
                    try:
                        feed = feedparser.parse(config['feed'])
                        if not feed.entries: continue
                        
                        # আমরা ফিডের পোস্ট চেক করব
                        # কিন্তু লজিক হলো: যতক্ষণ না পুরনো 'last_id' পাচ্ছি, ততক্ষণ পর্যন্ত নতুন পোস্ট
                        
                        new_posts = []
                        last_id = config.get('last_id')
                        
                        # প্রথম ৫টি পোস্ট চেক করি (যাতে একসাথে একাধিক পোস্ট দিলেও মিস না হয়)
                        for entry in feed.entries[:5]:
                            uid = entry.id if 'id' in entry else clean_url(entry.link)
                            
                            if uid == last_id:
                                break # পুরনো পোস্ট পেয়ে গেছি, আর খোঁজার দরকার নেই
                            
                            new_posts.append((entry, uid))
                        
                        # new_posts লিস্টে এখন সব নতুন পোস্ট আছে
                        # কিন্তু এগুলো রিভার্স করতে হবে যাতে আগেরটা আগে পোস্ট হয়
                        if new_posts:
                            for entry, uid in reversed(new_posts):
                                success = await send_post(config, entry)
                                if success:
                                    # সাকসেস হলে last_id আপডেট করে দাও
                                    config['last_id'] = uid
                                    changes = True
                                    await asyncio.sleep(2) # এক সাথে অনেক পোস্ট হলে একটু গ্যাপ দেবে
                                    
                    except Exception as e:
                        logger.error(f"Feed Error: {e}")
            
            if changes:
                save_data()
            
            await asyncio.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            await asyncio.sleep(10)

async def main():
    await bot.start()
    asyncio.create_task(checker_loop())
    await idle()
    await bot.stop()

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    bot.run(main())
