"""Download the reference tooth figure for the app's tooth guide, with its licence details.

    python scripts/fetch_tooth_figure.py

The figure is a real published illustration, not one we drew: Fig. 1005, "Vertical section
of a tooth in situ", from Henry Gray, *Anatomy of the Human Body* (20th edition, 1918),
public domain, as hosted on Wikimedia Commons (File:Gray1005.png). The script asks Commons
for the file's licence and refuses anything that is not public domain or a CC licence that
allows reuse. It writes src/weanage/web/figures/tooth_gray1005.png and the credit file
figures/tooth.json, which the app shows under the figure and in the About panel.
"""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

FILE = "File:Gray1005.png"
OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "web" / "figures"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "WeanAge/0.2 (https://github.com/andymaehartley/repotest)"}
ALLOWED = ("public domain", "pd", "cc0", "cc by", "cc-by")

# WeanAge terms placed over the figure (x and y in % of the image), added after checking
# where each part of the tooth is in the downloaded image.
LABELS: list[dict] = []


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return response.read()


def plain(html):
    """Commons metadata can contain HTML; keep only the text."""
    return re.sub(r"<[^>]+>", "", html or "").strip()


def main():
    query = urllib.parse.urlencode({"action": "query", "titles": FILE, "prop": "imageinfo",
                                    "iiprop": "url|extmetadata", "format": "json"})
    page = next(iter(json.loads(get(f"{API}?{query}"))["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise SystemExit(f"{FILE} was not found on Wikimedia Commons")
    info = page["imageinfo"][0]
    meta = {key: plain(value.get("value")) for key, value in info.get("extmetadata", {}).items()}
    licence = meta.get("LicenseShortName", "")
    if not licence.lower().startswith(ALLOWED):
        raise SystemExit(f"Licence '{licence}' does not clearly allow reuse; not downloading")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tooth_gray1005.png").write_bytes(get(info["url"]))
    credit = {
        "available": True,
        "file": "tooth_gray1005.png",
        "title": "Gray's Anatomy of the Human Body (1918), Fig. 1005: Vertical section of a tooth in situ",
        "author": meta.get("Artist") or "Henry Vandyke Carter / Henry Gray",
        "licence": licence,
        "source_url": info["descriptionurl"],
        "description": meta.get("ImageDescription", ""),
        "caption": "A human tooth. Livestock molars have the same parts, with much taller crowns.",
        "labels": LABELS,
    }
    (OUT / "tooth.json").write_text(json.dumps(credit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved the figure ({licence}) from {info['descriptionurl']} to {OUT}")


if __name__ == "__main__":
    main()
