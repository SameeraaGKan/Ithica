"""Pull every upload from the FaZe Clan channel, print the most-viewed videos, and
suggest a video_id for each lore entry that doesn't have one. Stdlib only.

Run from backend/:
    export YOUTUBE_API_KEY="..."
    python -m scripts.ingest_youtube            # print top videos + suggestions
    python -m scripts.ingest_youtube --write    # also save uploads into lore_seed.json `video_index`
    python -m scripts.load_lore                 # then push lore + video_index to Atlas

Quota: ~1 unit per 50 videos (playlistItems) + 1 per 50 (videos.list). ~2k uploads ≈ 80 units.
Review suggestions by eye, then paste video_id + start_s/end_s into data/lore_seed.json and set verified=true.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

SEED = pathlib.Path(__file__).resolve().parent.parent / "data" / "lore_seed.json"
API = "https://www.googleapis.com/youtube/v3/"
HANDLE = os.environ.get("FAZE_HANDLE", "@FaZeClan")

# Same era ids as app/schemas.py ERAS
ERA_BY_YEAR = [(2012, "2010_trickshots"), (2019, "2013_rug_era"), (2021, "2020_nuke_squad"), (2023, "2022_snoop"), (9999, "today")]


def era_for(year):
    return next(e for y, e in ERA_BY_YEAR if year <= y)


def get(path, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    with urllib.request.urlopen(API + path + "?" + urllib.parse.urlencode(params), timeout=30) as r:
        return json.load(r)


def uploads():
    ch = get("channels", part="contentDetails,snippet", forHandle=HANDLE)["items"][0]
    pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"channel: {ch['snippet']['title']}  uploads playlist: {pl}", file=sys.stderr)
    token = None
    while True:
        page = get("playlistItems", part="contentDetails", playlistId=pl, maxResults=50,
                   **({"pageToken": token} if token else {}))
        ids = [i["contentDetails"]["videoId"] for i in page["items"]]
        if ids:
            for v in get("videos", part="snippet,statistics", id=",".join(ids))["items"]:
                pub = v["snippet"]["publishedAt"]
                yield {
                    "video_id": v["id"], "channel": ch["snippet"]["title"],
                    "title": v["snippet"]["title"], "published_at": pub[:10],
                    "views": int(v["statistics"].get("viewCount", 0)),
                    "era": era_for(int(pub[:4])),
                }
        token = page.get("nextPageToken")
        if not token:
            return


def tokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower())) - {"faze", "clan", "the", "a", "of"}


def suggest(videos, lore):
    for e in lore["lore_entries"]:
        if e.get("video_id") or not e.get("find_video"):
            continue
        want = tokens(e["find_video"])
        cands = [v for v in videos if abs(int(v["published_at"][:4]) - e["year"]) <= 1] or videos
        best = sorted(cands, key=lambda v: (len(want & tokens(v["title"])), v["views"]), reverse=True)[:3]
        print(f"\n{e['id']}  ({e['year']})  looking for: {e['find_video']}")
        for v in best:
            print(f"   {v['video_id']}  {v['published_at'][:10]}  {v['views']:>11,}  {v['title']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="save uploads into lore_seed.json video_index")
    a = ap.parse_args()
    if not os.environ.get("YOUTUBE_API_KEY"):
        sys.exit("missing YOUTUBE_API_KEY")
    videos = list(uploads())
    print(f"fetched {len(videos)} videos", file=sys.stderr)
    top = sorted(videos, key=lambda v: v["views"], reverse=True)[:5]
    print("\nMost-viewed (check the pitch's 12.1M claim here):")
    for v in top:
        print(f"   {v['views']:>11,}  {v['published_at'][:10]}  {v['title']}  https://youtu.be/{v['video_id']}")
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    if a.write:
        seed["video_index"] = videos
        SEED.write_text(json.dumps(seed, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {len(videos)} videos to {SEED.name} video_index", file=sys.stderr)
    suggest(videos, seed)


if __name__ == "__main__":
    main()
