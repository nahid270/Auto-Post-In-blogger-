import feedparser
import requests
import time
import threading
from flask import Flask
import os

# ================= কনফিগারেশন (আপনার তথ্য দিন) =================
# ১. আপনার বটের টোকেন
BOT_TOKEN = "8536336775:AAESxUalVaN4ABnzlgCdVLqa9dyGDwY_cUQ"

# ২. আপনার চ্যানেলের ইউজারনেম (@ সহ)
CHANNEL_ID = "@CineZoneBD1"

# ৩. আপনার ব্লগের ফিড লিংক
RSS_FEED_URL = "https://banglaflix4k.blogspot.com/feeds/posts/default"

# ৪. চেক করার সময় (সেকেন্ডে) - এখন ১৫ সেকেন্ড দেওয়া হলো
CHECK_INTERVAL = 15 
# ============================================================

app = Flask(__name__)
last_posted_link = None

def send_to_telegram(title, link, image_url):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    # ক্যাপশন স্টাইল (ইচ্ছামতো ইমোজি বদলাতে পারেন)
    caption = f"🎬 <b>{title}</b>\n\n🔥 Watch Now:\n{link}\n\nJoin our Channel!"
    
    payload = {
        'chat_id': CHANNEL_ID,
        'caption': caption,
        'parse_mode': 'HTML',
        'photo': image_url
    }
    
    try:
        r = requests.post(api_url, data=payload)
        if r.status_code == 200:
            print(f"✅ Post Sent Successfully: {title}")
        else:
            # যদি ছবি সেন্ড করতে সমস্যা হয়, তবে শুধু টেক্সট পাঠাবে
            payload.pop('photo')
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={'chat_id': CHANNEL_ID, 'text': caption, 'parse_mode': 'HTML'})
            print(f"⚠️ Photo failed, sent text only. Error: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_feed():
    global last_posted_link
    print("Bot started watching for new movies... (Checking every 15 seconds)")
    
    # বট চালু হওয়ার সময় লাস্ট পোস্টটি মনে রাখবে, যাতে পুরনো পোস্ট আবার না যায়
    try:
        feed = feedparser.parse(RSS_FEED_URL)
        if feed.entries:
            last_posted_link = feed.entries[0].link
            print(f"Initial setup done. Last post found: {feed.entries[0].title}")
    except:
        pass

    while True:
        try:
            feed = feedparser.parse(RSS_FEED_URL)
            if feed.entries:
                latest_post = feed.entries[0]
                current_link = latest_post.link
                
                # যদি নতুন লিংক পাওয়া যায় এবং আগেরটার সাথে না মিলে
                if last_posted_link and current_link != last_posted_link:
                    print(f"New post detected! Processing: {latest_post.title}")
                    
                    title = latest_post.title
                    
                    # ব্লগের হাই-কোয়ালিটি ছবি বের করার লজিক
                    image_url = ""
                    if 'media_thumbnail' in latest_post:
                        # s72-c (ছোট) কে s1600 (বড়) তে কনভার্ট করা
                        image_url = latest_post.media_thumbnail[0]['url'].replace('s72-c', 's1600') 
                    
                    # টেলিগ্রামে পাঠানো
                    send_to_telegram(title, current_link, image_url)
                    
                    # আপডেট করা
                    last_posted_link = current_link
                
                # যদি একদম প্রথমবার রান হয় (last_posted_link None থাকে)
                elif last_posted_link is None:
                     last_posted_link = current_link

            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            print(f"Error checking feed: {e}")
            time.sleep(15) # এরর হলে ১৫ সেকেন্ড অপেক্ষা করবে

# রেন্ডারে সার্ভার চালু রাখার জন্য
@app.route('/')
def home():
    return "Movie Bot is Checking every 15 seconds!"

def run_bot():
    t = threading.Thread(target=check_feed)
    t.start()

if __name__ == "__main__":
    run_bot()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
