import os
import re
import html
import time
import random
import requests
from datetime import datetime, timezone, timedelta

API = "https://mastodon.social"
TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

MAX_REPLIES_PER_DAY = 10
TARGET_URL = "https://fosstodon.org/@chrisn/117568462618314747"
CHRISN_ACCOUNT = "chrisn@fosstodon.org"

BLOG = "https://antiatlasdev-apps.blogspot.com/"

SEARCH_TERMS = [
    # Network & Security
    "VPN recommendation", "VPN suggestions", "VPN not working",
    "WireGuard help", "OpenVPN help", "Proxy client", "SOCKS5 proxy",
    "looking for VPN", "DNS problem", "DNS Changer", "DNS leak",
    "SSL certificate check", "DNSTT check", "Slow DNS tunnel",
    "Subdomain finder", "Port scanner android",
    
    # Location & GPS
    "Mock location", "Fake GPS", "Spoof location android",
    "GPS route simulator", "Offline maps", "GPS not working",
    
    # Image Editing
    "Image resizer", "Background eraser", "Image converter",
    "Crop image android", "Compress image without losing quality",
    
    # Utilities & Health
    "File explorer android", "WiFi analyzer", "Speed test",
    "Network toolkit", "Calorie calculator", "Calorie tracker"
]

TOPIC = re.compile(
    r"\b(vpn|virtual private network|dns|doh|dot|"
    r"proxy|shadowsocks|wireguard|openvpn|v2ray|"
    r"image|photo|resize|crop|background|gps|location|"
    r"map|wifi|network|speed test|calorie|diet|file explorer)\b",
    re.I,
)

SENSITIVE = re.compile(
    r"\b(election|politics|political|fascist|fascists|"
    r"nazi|nazis|religion|religious|suicide|"
    r"self.harm|terrorism)\b",
    re.I,
)

PROMO = re.compile(
    r"\b(black friday|cyber monday|discount|coupon|"
    r"promo code|special offer|limited offer|"
    r"sponsored|affiliate|referral code|"
    r"buy now|save \d+%|deal of the day)\b",
    re.I,
)

NEWS = re.compile(
    r"\b(tl;dr|news roundup|news digest|"
    r"cbc reports|according to the article|"
    r"the article could not be read)\b",
    re.I,
)

REQUEST = re.compile(
    r"\b(any recommendations?|any suggestions?|"
    r"recommend me|recommendations for|"
    r"need.{0,30}recommendations?|"
    r"can anyone recommend|could someone recommend|"
    r"what vpn should i use|which vpn should i use|"
    r"which vpn do you recommend|looking for|"
    r"need help|help me|how do i fix|how can i fix|"
    r"does anyone know how to fix|any idea why|"
    r"what is causing|vpn alternatives|"
    r"alternative to proton|alternative to nordvpn)\b",
    re.I,
)

PROBLEM = re.compile(
    r"\b(not working|doesn't work|does not work|"
    r"broken|failing|failed|keeps disconnecting|"
    r"cannot connect|can't connect|"
    r"connection problem|connection error|"
    r"dns leak|dns resolution problem)\b",
    re.I,
)

CHRISN_REPLY = (
    "Thanks for sharing. If you're comparing VPN providers, "
    "Mullvad and IVPN are worth considering. I'm an independent "
    "Android developer at AntiAtlasDev. I build Android VPN "
    "clients and networking tools, including WireGuard, OpenVPN, "
    "DNS and proxy tools. These are apps, not VPN server "
    "subscriptions. Explore them here:\n"
    + BLOG
)

def headers():
    return {"Authorization": f"Bearer {TOKEN}"}

def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def is_chrisn_post(post):
    if post.get("url") == TARGET_URL:
        return True
    account = post.get("account", {}).get("acct", "").lower()
    text = clean_text(post.get("content", "")).lower()
    same_account = (
        account == CHRISN_ACCOUNT
        or account == "chrisn"
        or account.startswith("chrisn@fosstodon.org")
    )
    related_post = (
        "proton" in text
        and ("recommend" in text or "suggest" in text)
    )
    return same_account and related_post

def classify(text):
    text = clean_text(text)
    if not TOPIC.search(text):
        return "UNRELATED"
    if SENSITIVE.search(text):
        return "SENSITIVE"
    if PROMO.search(text):
        return "PROMOTIONAL"
    if NEWS.search(text):
        return "NEWS"
    if REQUEST.search(text):
        return "HELP_REQUEST"
    if PROBLEM.search(text):
        return "TECHNICAL_PROBLEM"
    return "GENERAL_DISCUSSION"

def get_account():
    response = requests.get(
        f"{API}/api/v1/accounts/verify_credentials",
        headers=headers(),
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

def search_posts(query):
    response = requests.get(
        f"{API}/api/v2/search",
        headers=headers(),
        params={
            "q": query,
            "type": "statuses",
            "limit": 10,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("statuses", [])

def parse_date(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)

def get_recent_activity(account_id):
    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    history_limit = since - timedelta(days=7)
    replied_ids = set()
    replied_accounts_today = set()
    daily_count = 0
    max_id = None

    for _ in range(10):
        params = {
            "limit": 40,
            "exclude_reblogs": "true",
        }
        if max_id:
            params["max_id"] = max_id
        response = requests.get(
            f"{API}/api/v1/accounts/{account_id}/statuses",
            headers=headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        statuses = response.json()
        if not statuses:
            break
        stop = False
        for status in statuses:
            created = parse_date(status["created_at"])
            if created < history_limit:
                stop = True
                break
            target_id = status.get("in_reply_to_id")
            if target_id:
                replied_ids.add(str(target_id))
                if created >= since:
                    daily_count += 1
                    author_id = status.get(
                        "account", {}
                    ).get("id")
                    if author_id:
                        replied_accounts_today.add(
                            str(author_id)
                        )
        max_id = statuses[-1]["id"]
        if stop:
            break
    return daily_count, replied_ids, replied_accounts_today

def build_reply(post, category):
    if is_chrisn_post(post):
        return CHRISN_REPLY
    
    if category in ("HELP_REQUEST", "TECHNICAL_PROBLEM"):
        replies = [
            "If you're looking for Android utilities, I'm an independent developer behind AntiAtlasDev. My apps include network tools, VPN clients, image editors, and GPS utilities. You can explore them here:\n" + BLOG,
            
            "I develop Android apps for networking and utilities (VPNs, DNS tools, GPS, image editing). You might find something useful here:\n" + BLOG,
            
            "As an Android dev, I build tools for network diagnostics, VPN connections, and media editing. Feel free to check out my apps here:\n" + BLOG,
            
            "If you're exploring Android networking or utility tools, I build VPN clients, DNS tools, and other apps. Check them out here:\n" + BLOG
        ]
        return random.choice(replies)
    
    return None

def publish_reply(post, message):
    if len(message) > 500:
        print(
            f"Skipped: reply is too long ({len(message)} characters).",
            flush=True,
        )
        return None
    response = requests.post(
        f"{API}/api/v1/statuses",
        headers=headers(),
        data={
            "status": message,
            "in_reply_to_id": str(post["id"]),
            "visibility": "public",
        },
        timeout=20,
    )
    if response.status_code not in (200, 201):
        print(
            f"Publish failed: HTTP {response.status_code} "
            f"{response.text[:300]}",
            flush=True,
        )
        return None
    return response.json()

def main():
    if not TOKEN:
        raise RuntimeError(
            "MASTODON_ACCESS_TOKEN is missing."
        )
    account = get_account()
    my_id = str(account["id"])
    print(
        f"Authenticated: @{account['acct']}",
        flush=True,
    )
    daily_count, replied_ids, replied_accounts = (
        get_recent_activity(my_id)
    )
    print(
        f"Replies today: {daily_count}/{MAX_REPLIES_PER_DAY}",
        flush=True,
    )
    if daily_count >= MAX_REPLIES_PER_DAY:
        print("Daily reply limit reached.", flush=True)
        return
    seen = {}
    for query in SEARCH_TERMS:
        try:
            for post in search_posts(query):
                if post.get("id"):
                    seen[str(post["id"])] = post
        except requests.RequestException as error:
            print(
                f"Search error ({query}): {error}",
                flush=True,
            )
    candidates = []
    for post in seen.values():
        account_data = post.get("account", {})
        author_id = str(account_data.get("id", ""))
        if author_id == my_id:
            continue
        if post.get("in_reply_to_id"):
            continue
        if post.get("visibility") not in (
            "public",
            "unlisted",
        ):
            continue
        content = clean_text(post.get("content", ""))
        category = classify(content)
        target = is_chrisn_post(post)
        if not target and category not in (
            "HELP_REQUEST",
            "TECHNICAL_PROBLEM",
        ):
            continue
        candidates.append((post, category, target))
    
    # Give Chrisn priority.
    candidates.sort(
        key=lambda item: not item[2]
    )
    published = 0
    for post, category, target in candidates:
        if daily_count + published >= MAX_REPLIES_PER_DAY:
            break
        post_id = str(post["id"])
        author_id = str(
            post.get("account", {}).get("id", "")
        )
        if post_id in replied_ids:
            continue
        if author_id in replied_accounts:
            continue
        message = build_reply(post, category)
        if not message:
            continue
        print(
            f"Replying to @{post['account'].get('acct', 'unknown')}",
            flush=True,
        )
        result = publish_reply(post, message)
        if result:
            published += 1
            replied_ids.add(post_id)
            replied_accounts.add(author_id)
            print(
                f"Published successfully: {result.get('url')}",
                flush=True,
            )
            # الانتظار لمدة دقيقة بين كل رد لتبدو طبيعية
            time.sleep(60)
            
    print(
        f"Finished. New replies: {published}. "
        f"Daily total: {daily_count + published}/"
        f"{MAX_REPLIES_PER_DAY}",
        flush=True,
    )

if __name__ == "__main__":
    main()
