import os
import json
import requests
from atproto import Client

TWITTER_HANDLE       = os.environ["TWITTER_HANDLE"]
TWITTER_BEARER_TOKEN = os.environ["TWITTER_BEARER_TOKEN"]
BLUESKY_HANDLE       = os.environ["BLUESKY_HANDLE"]
BLUESKY_PASSWORD     = os.environ["BLUESKY_PASSWORD"]

STATE_FILE = "seen_ids.json"
HEADERS    = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}

def load_seen():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def get_user_id(handle):
    url = f"https://api.twitter.com/2/users/by/username/{handle}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 429:
        print("Rate-limited by Twitter — skipping.")
        return None
    r.raise_for_status()
    return r.json()["data"]["id"]

def fetch_tweets(user_id):
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    params = {"exclude": "retweets,replies", "max_results": 5}
    r = requests.get(url, headers=HEADERS, params=params)
    if r.status_code == 429:
        print("Rate-limited by Twitter — skipping.")
        return []
    r.raise_for_status()
    return r.json().get("data", [])

def main():
    seen = load_seen()
    user_id = get_user_id(TWITTER_HANDLE)
    if not user_id:
        return
    tweets = fetch_tweets(user_id)
    print(f"Fetched {len(tweets)} tweets from @{TWITTER_HANDLE}")
    if not tweets:
        return
    bsky = Client()
    bsky.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    new_ids = set()
    for tweet in reversed(tweets):
        tid, text = tweet["id"], tweet["text"]
        if tid in seen:
            continue
        print(f"→ Reposting: {text[:80]}")
        try:
            bsky.send_post(text=text)
            print(f"✅ Posted: {text[:80]}")
            new_ids.add(tid)
        except Exception as e:
            print(f"❌ Failed: {e}")
    seen.update(new_ids)
    save_seen(seen)

if __name__ == "__main__":
    main()
