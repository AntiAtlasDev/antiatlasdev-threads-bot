
import os
import re
import html
import requests

API_URL = "https://mastodon.social"
TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")

SEARCH_TERMS = [
    "Android VPN",
    "WireGuard",
    "OpenVPN",
    "Android DNS",
    "Android GPS",
    "Android firewall",
    "mock location",
    "Android proxy"
]

TOPICS = [
    "android vpn", "vpn", "wireguard", "openvpn",
    "shadowsocks", "v2ray", "xray", "proxy",
    "dns", "firewall", "mock location",
    "gps spoofing", "gps simulator",
    "location simulator", "android app",
    "android apps", "mobile app", "mobile apps"
]

PROMO_PHRASES = [
    "sponsored", "affiliate link", "promo code",
    "buy now", "limited offer", "giveaway",
    "discount code", "advertisement",
    "introducing our", "meet our new",
    "download now", "available now",
    "check out our", "get started today",
    "features include", "launching our"
]

HELP_PHRASES = [
    "need help", "please help",
    "can someone help", "could someone help",
    "how do i", "how can i",
    "how do i fix", "how can i fix",
    "anyone know", "does anyone know",
    "can anyone recommend",
    "any recommendations",
    "which app", "any alternative",
    "any solution", "is there a way",
    "is it possible", "why does",
    "why is", "looking for help",
    "has anyone experienced"
]

PROBLEM_PHRASES = [
    "not working", "doesn't work",
    "does not work", "can't connect",
    "cannot connect", "unable to connect",
    "connection problem", "connection issue",
    "having trouble", "having problems",
    "keeps crashing", "app crashes",
    "error when", "failed to connect",
    "doesn't connect", "stopped working",
    "broken after", "getting an error"
]


def clean_text(content):
    content = re.sub(r"<[^>]+>", " ", content)
    content = html.unescape(content)
    content = re.sub(r"https?://\S+", " ", content)
    return re.sub(r"\s+", " ", content).strip().lower()


def score_post(content):
    text = clean_text(content)

    if any(phrase in text for phrase in PROMO_PHRASES):
        return 0, ["Promotional content"]

    matched_topics = [
        word for word in TOPICS if word in text
    ]

    if not matched_topics:
        return 0, ["No relevant technical topic"]

    has_help = any(
        phrase in text for phrase in HELP_PHRASES
    )

    has_problem = any(
        phrase in text for phrase in PROBLEM_PHRASES
    )

    if not has_help and not has_problem:
        return 0, [
            "No clear help request or technical problem"
        ]

    score = 5
    reasons = [
        "Relevant topic: " + ", ".join(matched_topics[:3])
    ]

    if has_help:
        score += 2
        reasons.append("Explicit help request")

    if has_problem:
        score += 2
        reasons.append("Specific technical problem")

    if "?" in text:
        score += 1
        reasons.append("Contains a question")

    return score, reasons


def main():
    if not TOKEN:
        print("ERROR: Missing access token.")
        return

    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    seen_ids = set()
    candidates = []

    for term in SEARCH_TERMS:
        print(f"\nSearching: {term}")

        try:
            response = requests.get(
                f"{API_URL}/api/v2/search",
                headers=headers,
                params={
                    "q": term,
                    "type": "statuses",
                    "limit": 10
                },
                timeout=30
            )

            print("HTTP Status:", response.status_code)

            if response.status_code != 200:
                print(
                    "Search failed:",
                    response.text[:300]
                )
                continue

            statuses = response.json().get(
                "statuses", []
            )

            for status in statuses:
                post_id = status.get("id")

                if not post_id or post_id in seen_ids:
                    continue

                seen_ids.add(post_id)

                raw_content = status.get(
                    "content", ""
                )

                score, reasons = score_post(
                    raw_content
                )

                if score < 5:
                    continue

                account = status.get("account", {})

                candidates.append({
                    "id": post_id,
                    "user": account.get(
                        "acct", "Unknown"
                    ),
                    "url": status.get("url", ""),
                    "text": clean_text(raw_content),
                    "score": score,
                    "reasons": reasons
                })

        except requests.RequestException as error:
            print(
                "Network error:",
                str(error)
            )

    print("\n========== FILTER RESULTS ==========")
    print("Unique posts checked:", len(seen_ids))
    print(
        "Potential conversations:",
        len(candidates)
    )

    for index, post in enumerate(candidates, 1):
        print(f"\nCandidate {index}")
        print("Score:", post["score"])
        print(
            "Reasons:",
            ", ".join(post["reasons"])
        )
        print("User:", post["user"])
        print("URL:", post["url"])
        print("Text:", post["text"][:400])

    print(
        "\nTest completed. No replies were published."
    )


if __name__ == "__main__":
    main()
