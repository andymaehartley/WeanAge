"""Download the tooth figure for the app's tooth guide from Wikimedia Commons, with its licence.

    python scripts/fetch_tooth_figure.py

The figure is a real, credited illustration, not one we drew: "Tooth Section" by Sam Fentress
(File:Tooth_Section.svg), CC BY-SA 2.0. A copy is already in src/weanage/web/figures/; this
script refreshes it. It asks Commons for the file's licence and refuses anything that is not
public domain or an open CC licence, saves a PNG rendering, and writes figures/tooth.json with
the credit and the WeanAge labels drawn over the figure.
"""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

FILE = "File:Tooth_Section.svg"
WIDTH = 708  # pixels; the label positions below are in % so any width works
OUT = Path(__file__).resolve().parents[1] / "src" / "weanage" / "web" / "figures"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "WeanAge/0.2 (https://github.com/andymaehartley/repotest)"}
ALLOWED = ("public domain", "pd", "cc0", "cc by")  # also matches "cc by-sa"

# WeanAge terms drawn over the figure: x and y in % of the image; `to` draws a line to a point.
LABELS = [
    {
        "text": "Cusp apex = 0 mm",
        "x": 53.7,
        "y": 6.3,
        "to": [
            53.7,
            10.9
        ]
    },
    {
        "text": "position_mm",
        "x": 10,
        "y": 8,
        "to": [
            10,
            24
        ],
        "arrow": True
    },
    {
        "text": "Cervix",
        "x": 8,
        "y": 38,
        "to": [
            30.4,
            42.6
        ]
    }
]


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as response:
        return response.read()


def plain(html):
    """Commons metadata can contain HTML; keep only the text."""
    return re.sub(r"<[^>]+>", "", html or "").strip()


def main():
    query = urllib.parse.urlencode({"action": "query", "titles": FILE, "prop": "imageinfo",
                                    "iiprop": "url|extmetadata", "iiurlwidth": WIDTH, "format": "json"})
    page = next(iter(json.loads(get(f"{API}?{query}"))["query"]["pages"].values()))
    if "imageinfo" not in page:
        raise SystemExit(f"{FILE} was not found on Wikimedia Commons")
    info = page["imageinfo"][0]
    meta = {key: plain(value.get("value")) for key, value in info.get("extmetadata", {}).items()}
    licence = meta.get("LicenseShortName", "")
    if not licence.lower().startswith(ALLOWED):
        raise SystemExit(f"Licence '{licence}' does not clearly allow reuse; not downloading")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "tooth_section_fentress.png").write_bytes(get(info["thumburl"]))
    credit = {
        "available": True,
        "file": "tooth_section_fentress.png",
        "title": "Tooth Section",
        "author": meta.get("Artist") or "Sam Fentress",
        "licence": licence,
        "licence_url": meta.get("LicenseUrl", ""),
        "source_url": info["descriptionurl"],
        "caption": "A human molar in section. Livestock molars have the same parts, with much taller crowns. "
                   "The figure is shown unchanged; the blue labels are WeanAge's terms, drawn over it.",
        "labels": LABELS,
    }
    (OUT / "tooth.json").write_text(json.dumps(credit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved the figure ({licence}) from {info['descriptionurl']} to {OUT}")


if __name__ == "__main__":
    main()
