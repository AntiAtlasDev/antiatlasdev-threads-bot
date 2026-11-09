
import os
import re
import html
import requests
from collections import Counter

API = "https://mastodon.social"
TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "VPN recommendation",
    "VPN suggestions",
    "VPN not working",
    "DNS problem",
    "WireGuard help",
    "looking for VPN",
]

TOPIC = re.compile(
    r"\b(vpn|virtual private network|dns|doh|dot|"
    r"proxy|shadowsocks|wireguard|openvpn|v2ray|"
    r"mock location|gps spoofing)\b",
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
    r"recommend me|can anyone recommend|"
    r"could someone recommend|"
    r"what vpn should i use|which vpn should i use|"
    r"which vpn do you recommend|"
    r"looking for|need help|help me|"
    r"how do i fix|how can i fix|"
    r"does anyone know how to fix|"
    r"any idea why|what is causing|"
    r"vpn alternatives|alternative to proton|"
    r"alternative to nordvpn)\b",
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


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


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


def search_posts(query):
    response = requests.get(
        f"{API}/api/v2/search",
        headers={"Authorization": f"Bearer {TOKEN}"},
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

    for query in SEARCH_TERMS:
        try:
            for post in search_posts(query):
                post_id = post.get("id")

                if post_id:
                    seen[str(post_id)] = post

        except requests.RequestException as error:
            print(f"Search error: {error}", flush=True)

    print(f"\nUnique posts: {len(seen)}", flush=True)

    counts = Counter()
    candidates = []

    for post in seen.values():
        content = clean_text(post.get("content", ""))
        category = classify(content)

        counts[category] += 1

        if category in (
            "HELP_REQUEST",
            "TECHNICAL_PROBLEM",
            "GENERAL_DISCUSSION",
        ):
            candidates.append((post, category))

    print("\nClassification:", flush=True)

    for category, count in sorted(counts.items()):
        print(f"{category}: {count}", flush=True)

    print(
        f"\nTechnical posts for review: {len(candidates)}",
        flush=True,
    )

    if not candidates:
        print("No technical posts found.", flush=True)

    for index, (post, category) in enumerate(candidates, 1):
        account = post.get("account", {})
        username = account.get("acct", "unknown")

        print("\n" + "=" * 45, flush=True)
        print(f"POST {index}", flush=True)
        print(f"Category: {category}", flush=True)
        print(f"Account: @{username}", flush=True)
        print(
            f"Text: {clean_text(post.get('content', ''))[:700]}",
            flush=True,
        )
        print(f"URL: {post.get('url', '')}", flush=True)

    print("\nFilter completed.", flush=True)
    print("No replies were published.", flush=True)


if __name__ == "__main__":
    main()
