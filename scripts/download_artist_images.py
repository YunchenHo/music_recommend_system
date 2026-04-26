"""
從 Wikipedia API 批量下載藝人圖片到 frontend/public/artists/
執行方式：在專案根目錄執行 python scripts/download_artist_images.py
"""

import requests
import time
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "frontend" / "public" / "artists"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "MusicRecommendApp/1.0 (https://github.com/test; chiu01816@gmail.com)"}

# (display_name, wikipedia_page_title, output_filename)
ARTISTS = [
    # Chinese Page2
    ("Jeff Chang",      "Jeff Chang",           "jeffchang.jpg"),
    ("S.H.E",           "S.H.E (group)",        "she.jpg"),
    ("Stefanie Sun",    "Stefanie Sun",          "stefaniesun.jpg"),
    ("Fish Leong",      "Fish Leong",            "fishleong.jpg"),
    ("Leehom Wang",     "Leehom Wang",           "leehomwang.jpg"),
    ("Rene Liu",        "Rene Liu",              "reneliu.jpg"),
    ("Tanya Chua",      "Tanya Chua",            "tanyachua.jpg"),
    ("Elva Hsiao",      "Elva Hsiao",            "elvahsiao.jpg"),
    # English Page2
    ("Coldplay",        "Coldplay",              "coldplay.jpg"),
    ("Katy Perry",      "Katy Perry",            "katyperry.jpg"),
    ("Imagine Dragons", "Imagine Dragons",       "imaginedragons.jpg"),
    ("Bon Jovi",        "Bon Jovi",              "bonjovi.jpg"),
    ("One Direction",   "One Direction",         "onedirection.jpg"),
    ("Adele",           "Adele",                 "adele.jpg"),
    ("Queen",           "Queen (band)",          "queen.jpg"),
    ("OneRepublic",     "OneRepublic",           "onerepublic.jpg"),
    # Japanese Page2
    ("Ayumi Hamasaki",  "Ayumi Hamasaki",        "ayumihamasaki.jpg"),
    ("GReeeeN",         "GReeeeN",               "greeeeen.jpg"),
    ("Do As Infinity",  "Do As Infinity",        "doasinfinity.jpg"),
    ("Ai Otsuka",       "Ai Otsuka",             "aiotsuka.jpg"),
    ("Kalafina",        "Kalafina",              "kalafina.jpg"),
    ("Mika Nakashima",  "Mika Nakashima",        "mikanakashima.jpg"),
    ("Tohoshinki",      "Tohoshinki",            "tohoshinki.jpg"),
    ("Nogizaka46",      "Nogizaka46",            "nogizaka46.jpg"),
    # Korean Page2
    ("TAEYANG",         "Taeyang",               "taeyang.jpg"),
    ("G-DRAGON",        "G-Dragon",              "gdragon.jpg"),
    ("f(x)",            "F(x) (group)",          "fx.jpg"),
    ("AOA",             "AOA (group)",           "aoa.jpg"),
    ("Apink",           "Apink",                 "apink.jpg"),
    ("ROY KIM",         "Roy Kim (singer)",      "roykim.jpg"),
    ("BIGBANG",         "Big Bang (South Korean band)", "bigbang.jpg"),
    ("AKMU",            "Akdong Musician",       "akmu.jpg"),
]


def get_wikipedia_thumbnail(page_title: str) -> str | None:
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(page_title)}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            thumb = data.get("thumbnail", {}).get("source")
            if thumb:
                # 把縮圖 URL 的寬度改成 400px，取得更大尺寸
                thumb = re.sub(r"/\d+px-", "/400px-", thumb)
            return thumb
    except Exception as e:
        print(f"  [API error] {e}")
    return None


def download_image(url: str, filepath: Path) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            filepath.write_bytes(resp.content)
            return True
    except Exception as e:
        print(f"  [download error] {e}")
    return False


def main():
    ok, fail, skip = [], [], []

    for display_name, wiki_title, filename in ARTISTS:
        out_path = OUTPUT_DIR / filename

        if out_path.exists():
            print(f"[SKIP] {display_name} -> {filename} (already exists)")
            skip.append(display_name)
            continue

        print(f"[...] {display_name} ...", end=" ", flush=True)
        img_url = get_wikipedia_thumbnail(wiki_title)

        if not img_url:
            print("FAIL (not found on Wikipedia)")
            fail.append(display_name)
        else:
            if download_image(img_url, out_path):
                print(f"OK -> {filename}")
                ok.append((display_name, filename))
            else:
                print("FAIL (download error)")
                fail.append(display_name)

        time.sleep(0.3)  # 避免打爆 Wikipedia

    print("\n" + "=" * 50)
    print(f"OK: {len(ok)}  SKIP: {len(skip)}  FAIL: {len(fail)}")

    if fail:
        print("\nNeeds manual handling:")
        for name in fail:
            print(f"  - {name}")

    if ok:
        print("\n--- image paths for JSX ---")
        for display_name, filename in ok:
            print(f'  // {display_name}  ->  image: "/artists/{filename}"')


if __name__ == "__main__":
    main()
