import os
import time
import random
from requests_oauthlib import OAuth1Session

# إعدادات API (سيتم جلبها من GitHub Secrets)
CONSUMER_KEY = os.environ.get("TUMBLR_CONSUMER_KEY")
CONSUMER_SECRET = os.environ.get("TUMBLR_CONSUMER_SECRET")
TOKEN = os.environ.get("TUMBLR_TOKEN")
TOKEN_SECRET = os.environ.get("TUMBLR_TOKEN_SECRET")

# اسم مدونتك على Tumblr (مثال: antiatlasdev.tumblr.com)
BLOG_NAME = os.environ.get("TUMBLR_BLOG_NAME", "antiatlasdev.tumblr.com")

# كلمات البحث للعثور على منشورات لإعادة تدوينها
SEARCH_TAGS = ["vpn", "android", "dns", "networking", "wireguard"]

def get_client():
    return OAuth1Session(
        CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=TOKEN,
        resource_owner_secret=TOKEN_SECRET
    )

def search_and_reblog():
    client = get_client()
    
    for tag in SEARCH_TAGS:
        print(f"Searching for tag: {tag}")
        
        url = "https://api.tumblr.com/v2/tagged"
        params = {"tag": tag, "limit": 5}
        
        try:
            response = client.get(url, params=params)
            response.raise_for_status()
            posts = response.json().get("response", [])
            
            for post in posts:
                # تجنب إعادة تدوين منشوراتك الخاصة
                if post.get("blog_name") == BLOG_NAME:
                    continue
                
                # التحقق من وجود reblog_key (ضروري لإعادة التدوين)
                if "reblog_key" not in post:
                    continue
                
                # نصوص التعليق (عشوائية)
                comments = [
                    "If you're into Android networking, I build open-source tools for VPNs and DNS. Check my blog!",
                    "Great post! I'm an Android dev working on network utilities. You might find my apps useful.",
                    "Thanks for sharing. I develop independent Android apps for networking and security."
                ]
                comment = random.choice(comments)
                
                # تنفيذ إعادة التدوين مع التعليق
                reblog_url = f"https://api.tumblr.com/v2/blog/{BLOG_NAME}/post/reblog"
                payload = {
                    "id": post["id"],
                    "reblog_key": post["reblog_key"],
                    "comment": comment
                }
                
                reblog_response = client.post(reblog_url, data=payload)
                
                if reblog_response.status_code == 201:
                    print(f"✅ Reblogged post {post['id']} from {post.get('blog_name')}")
                    time.sleep(60) # انتظار دقيقة بين كل إعادة تدوين
                    return True # نكتفي بإعادة تدوين واحد في كل تشغيل
                else:
                    print(f"❌ Failed to reblog: {reblog_response.text}")
                    
        except Exception as e:
            print(f"Error searching tag {tag}: {e}")
    
    print("No suitable posts found for reblogging.")
    return False

if __name__ == "__main__":
    print("AntiAtlasDev Tumblr Bot")
    success = search_and_reblog()
    if success:
        print("Finished successfully.")
    else:
        print("Finished with no action.")
