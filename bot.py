
import os
import requests

GRAPH_URL = "https://graph.threads.net"
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")


def check_token():
    if not ACCESS_TOKEN:
        print("ERROR: THREADS_ACCESS_TOKEN is not configured.")
        return False

    try:
        response = requests.get(
            f"{GRAPH_URL}/v1.0/me",
            params={
                "fields": "id,username",
                "access_token": ACCESS_TOKEN
            },
            timeout=30
        )

        print("HTTP status:", response.status_code)

        if response.ok:
            data = response.json()
            print("Connected Threads account:", data.get("username"))
            return True

        print("Threads API error:", response.text[:500])
        return False

    except requests.RequestException as error:
        print("Connection error:", str(error))
        return False


if __name__ == "__main__":
    if check_token():
        print("Threads connection test successful.")
    else:
        print("Threads connection test failed.")
      
