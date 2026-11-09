
import os
import requests

MASTODON_URL = "https://mastodon.social"
ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")


def main():
    if not ACCESS_TOKEN:
        print("ERROR: MASTODON_ACCESS_TOKEN is missing.")
        return

    print("Checking Mastodon connection...")

    try:
        response = requests.get(
            f"{MASTODON_URL}/api/v1/accounts/verify_credentials",
            headers={
                "Authorization": f"Bearer {ACCESS_TOKEN}"
            },
            timeout=30
        )

        print("HTTP Status:", response.status_code)

        if response.status_code == 200:
            account = response.json()
            print("Connection successful!")
            print("Username:", account.get("username"))
            print("Account ID:", account.get("id"))
        else:
            print("Connection failed.")
            print("Server response:", response.text[:500])

    except requests.RequestException as error:
        print("Network error:", str(error))


if __name__ == "__main__":
    main()
