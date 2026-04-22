import os, json, requests
from atproto import Client, models

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
    except: return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def get_user_id(handle):
    r = requests.get(f"https://api.twitter.com/2/users/by/username/{handle}", headers=HEADERS)
    if r.status_code == 429: print("Rate-limited"); return None
    r.raise_for_status()
    return r.json()["data"]["id"]

def fetch_tweets(user_id):
    params = {"exclude":"retweets,replies","max_results":5,"expansions":"attachments.media_keys","media.fields":"url,type"}
    r = requests.get(f"https://api.twitter.com/2/users/{user_id}/tweets", headers=HEADERS, params=params)
    if r.status_code == 429: return [], {}
    r.raise_for_status()
    data = r.json()
    media_map = {m["media_key"]: m["url"] for m in data.get("includes",{}).get("media",[]) if m["type"]=="photo" and "url" in m}
    return data.get("data",[]), media_map

def upload_images(bsky, media_keys, media_map):
    blobs = []
    for key in media_keys[:4]:
        url = media_map.get(key)
        if not url: continue
        try:
            img_data = requests.get(url, timeout=10).content
            mime = "image/png" if url.endswith(".png") else "image/jpeg"
            resp = bsky.upload_blob(img_data)
            blobs.append(models.AppBskyEmbedImages.Image(alt="", image=resp.blob))
            print(f"  Uploaded image: {url}")
        except Exception as e:
            print(f"  Image upload failed: {e}")
    return blobs

def main():
    seen = load_seen()
    user_id = get_user_id(TWITTER_HANDLE)
    if not user_id: return
    tweets, media_map = fetch_tweets(user_id)
    print(f"Fetched {len(tweets)} tweets from @{TWITTER_HANDLE}")
    if not tweets: return
    bsky = Client()
    bsky.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
    new_ids = set()
    for tweet in reversed(tweets):
        tid, text = tweet["id"], tweet["text"]
        if tid in seen: continue
        print(f"-> Reposting: {text[:80]}")
        media_keys = tweet.get("attachments",{}).get("media_keys",[])
        embed = None
        if media_keys:
            blobs = upload_images(bsky, media_keys, media_map)
            if blobs: embed = models.AppBskyEmbedImages.Main(images=blobs)
        try:
            bsky.send_post(text=text, embed=embed)
            print(f"Posted: {text[:80]}")
            new_ids.add(tid)
        except Exception as e:
            print(f"Failed: {e}")
    seen.update(new_ids)
    save_seen(seen)
    print(f"Done. {len(new_ids)} new post(s) mirrored.")

if __name__ == "__main__":
    main()
