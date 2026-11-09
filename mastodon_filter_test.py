
import os
import re
import html
import requests

API = "https://mastodon.social"
TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "VPN recommendation",
    "VPN not working",
    "DNS problem",
]

TOPIC = re.compile(
    r"\b(vpn|virtual private network|dns|dns over https|"
    r"doh|dot|proxy|shadowsocks|wireguard|openvpn|"
    r"v2ray|gps spoofing|mock location)\b",
    re.I,
)

# طلب صريح لتوصية أو مساعدة
REQUEST = re.compile(
    r"\b("
    r"anyone know (?:a )?(?:good|reliable|stable)?\s*(?:vpn|proxy)|"
    r"any recommendations? for (?:a |an )?(?:vpn|proxy)|"
    r"can anyone recommend|"
    r"could someone recommend|"
    r"which vpn (?:should|would) i use|"
    r"what vpn should i use|"
    r"looking for (?:a |an )?(?:vpn|proxy)|"
    r"i need (?:a |an )?(?:vpn|proxy)|"
    r"need help with|"
    r"any help with|"
    r"how do i fix|"
    r"how can i fix|"
    r"does anyone know how to fix|"
    r"vpn alternatives|"
    r"alternative to proton vpn|"
    r"alternative to nordvpn"
    r")\b",
    re.I,
)

# مشكلة تقنية يصفها صاحب المنشور
PROBLEM = re.compile(
    r"\b("
    r"(?:vpn|proxy|dns) (?:is |isn't |is not )?"
    r"(?:not working|broken|down|failing|slow)|"
    r"can't connect to (?:the )?(?:vpn|proxy)|"
    r"cannot connect to (?:the )?(?:vpn|proxy)|"
    r"vpn connection (?:fails|failed|keeps dropping)|"
    r"dns (?:isn't resolving|is not resolving|"
    r"not resolving|resolution problem)|"
    r"dns leak|"
    r"wireguard (?:doesn't connect|not connecting)|"
    r"openvpn (?:doesn't connect|not connecting)"
    r")\b",
    re.I,
)

SENSITIVE = re.compile(
    r"\b("
    r"election|politics|political|fascist|fascists|"
    r"nazi|nazis|religion|religious|suicide|"
    r"self.harm|terrorism"
    r")\b",
    re.I,
)

PROMO = re.compile(
    r"\b("
    r"black friday|cyber monday|discount|coupon|"
    r"promo code|special offer|limited offer|"
    r"sponsored|affiliate|referral code|"
    r"buy now|save \d+%|deal of the day"
    r")\b",
    re.I,
)

NEWS_DIGEST = re.compile(
    r"\b("
    r"tl;dr|cbc reports|according to the article|"
    r"the article could not be read|news digest|"
    r"daily news roundup"
    r")\b",
    re.I,
)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}

session = requests.Session()


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def classify(text):
    text = clean_text(text)

    if not TOPIC.search(text):
        return "UNRELATED"

    if SENSITIVE.search(text):
        return "SENSITIVE"

    if PROMO.search(text):
        return "PROMOTIONAL"

    if NEWS_DIGEST.search(text):
        return "NEWS"

    # يجب أن يكون طلب التوصية أو المساعدة صريحاً
    if REQUEST.search(text):
        return "HELP_REQUEST"

    # مشكلة تقنية واضحة وليست مجرد ذكر للموضوع
    if PROBLEM.search(text):
        return "TECHNICAL_PROBLEM"

    return "GENERAL_DISCUSSION"


def search_posts(query):
    url = f"{API}/api/v2/search"

    response = session.get(
        url,
        headers=HEADERS,
        params={
            "q": query,
            "type": "statuses",
            "limit": 10,
        },
        timeout=(3, 5),
    )

    print(f"{query}: HTTP {response.status_code}", flush=True)
    response.raise_for_status()

    return response.json().get("statuses", [])


def main():
    if not TOKEN:
        print("ERROR: MASTODON_ACCESS_TOKEN is missing.")
        return

    seen = {}
    counts = {}

    for query in SEARCH_TERMS:
        try:
            posts = search_posts(query)

            for post in posts:
                post_id = post.get("id")

                if not post_id:
                    continue

                seen[post_id] = post

        except requests.RequestException as error:
            print(f"Search error: {error}", flush=True)

    print(f"\nUnique posts: {len(seen)}", flush=True)

    candidates = []

    for post in seen.values():
        text = clean_text(post.get("content", ""))
        category = classify(text)

        counts[category] = counts.get(category, 0) + 1

        if category in ("HELP_REQUEST", "TECHNICAL_PROBLEM"):
            candidates.append((post, category))

    print("\nClassification:", flush=True)

    for category, count in sorted(counts.items()):
        print(f"{category}: {count}", flush=True)

    print("\nPotential replies:", flush=True)

    if not candidates:
        print("No suitable posts found.", flush=True)

    for post, category in candidates:
        account = post.get("account", {})
        username = account.get("acct", "unknown")
        text = clean_text(post.get("content", ""))
        url = post.get("url", "")

        print("\n-------------------------", flush=True)
        print(f"Category: {category}", flush=True)
        print(f"Account: @{username}", flush=True)
        print(f"Post: {text[:500]}", flush=True)
        print(f"URL: {url}", flush=True)

    print("\nFilter completed. No replies were published.", flush=True)


if __name__ == "__main__":
    main()
