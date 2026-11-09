
import os
import re
import html
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

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

DAILY_LIMIT = 5
STATE_FILE = Path("mastodon_bot_state.json")

TOPIC = re.compile(
    r"\b(vpn|virtual private network|dns|doh|dot|"
    r"proxy|shadowsocks|wireguard|openvpn|v2ray|"
    r"mock location|gps spoofing)\b",
    re.I,
)

REQUEST = re.compile(
    r"\b("
    r"any recommendations?|any suggestions?|"
    r"recommend me|can anyone recommend|"
    r"could someone recommend|"
    r"what vpn should i use|which vpn should i use|"
    r"which vpn do you recommend|"
    r"looking for (?:a |an )?(?:good |reliable |stable )?(?:vpn|proxy)|"
    r"need (?:a |an )?(?:good |reliable |stable )?(?:vpn|proxy)|"
    r"vpn alternatives|alternative to proton|"
    r"alternative to nordvpn|"
    r"anyone know a good vpn|"
    r"need help with|help me with|"
    r"how do i fix|how can i fix|"
    r"does anyone know how to fix|"
    r"any idea why|"
    r"what is causing"
    r")\b",
    re.I,
)

PROBLEM = re.compile(
    r"\b("
    r"(?:vpn|proxy|dns|wireguard|openvpn)"
    r".{0,35}"
    r"(?:not working|doesn't work|does not work|"
    r"broken|failing|failed|keeps disconnecting|"
    r"cannot connect|can't connect|"
    r"connection problem|connection error)|"
    r"(?:not working|doesn't work|does not work|"
    r"cannot connect|can't connect)"
    r".{0,35}"
    r"(?:vpn|proxy|dns|wireguard|openvpn)|"
    r"dns leak|dns resolution problem"
    r")",
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


def load_state():
    if not STATE_FILE.exists():
        return {
            "replied_ids": [],
            "daily_count": 0,
            "date": "",
        }

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {
            "replied_ids": [],
            "daily_count": 0,
            "date": "",
        }


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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

    state = load_state()
    today = datetime.now(timezone.utc).date().isoformat()

    if state.get("date") != today:
        state["date"] = today
        state["daily_count"] = 0

    seen = {}

    for query in SEARCH_TERMS:
        try:
            for post in search_posts(query):
                post_id = post.get("id")
                if post_id:
                    seen[post_id] = post
        except requests.RequestException as error:
            print(f"Search error: {error}", flush=True)

    print(f"\nUnique posts: {len(seen)}", flush=True)

    counts = {}
    candidates = []

    replied_ids = set(state.get("replied_ids", []))

    for post in seen.values():
        post_id = str(post.get("id"))
        text = clean_text(post.get("content", ""))
        category = classify(text)

        counts[category] = counts.get(category, 0) + 1

        if category not in (
            "HELP_REQUEST",
            "TECHNICAL_PROBLEM",
        ):
            continue

        if post_id in replied_ids:
            continue

        candidates.append((post, category))

    print("\nClassification:", flush=True)

    for category, count in sorted(counts.items()):
        print(f"{category}: {count}", flush=True)

    print("\nPotential replies:", flush=True)

    if not candidates:
        print("No suitable posts found.", flush=True)

    for post, category in candidates:
        account = post.get("account", {})
        print("\n-------------------------", flush=True)
        print(f"Category: {category}", flush=True)
        print(f"Account: @{account.get('acct', 'unknown')}", flush=True)
        print(f"Post: {clean_text(post.get('content', ''))[:500]}", flush=True)
        print(f"URL: {post.get('url', '')}", flush=True)

    print(
        f"\nDaily limit: {DAILY_LIMIT} replies",
        flush=True,
    )
    print(
        f"Already replied today: {state.get('daily_count', 0)}",
        flush=True,
    )

    print(
        "\nFilter completed. No replies were published.",
        flush=True,
    )


if __name__ == "__main__":
    main()
