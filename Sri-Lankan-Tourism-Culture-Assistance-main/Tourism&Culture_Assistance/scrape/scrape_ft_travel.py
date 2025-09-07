#!/usr/bin/env python3
"""
scrape_ft_travel.py

Scrapes the FT.lk Travel / Tourism listing (https://www.ft.lk/travel-tourism/27)
or a local saved copy of its page (view-source_https___www.ft.lk_travel-tourism_27.html)

Saves results to output/ft_travel_tourism.csv and downloads images to output/images/

Fields: title, date, listing_url, description, thumbnail_url, article_image_urls, image_files
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os, time, random, re
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from urllib.robotparser import RobotFileParser

BASE = "https://www.ft.lk"
LISTING = "https://www.ft.lk/travel-tourism/27"
LOCAL_SOURCE = "/mnt/data/view-source_https___www.ft.lk_travel-tourism_27.html"

OUT_DIR = Path("output")
IM_DIR = OUT_DIR / "images"
CSV_PATH = OUT_DIR / "ft_travel_tourism.csv"
USER_AGENT = "Mozilla/5.0 (compatible; ft-scraper/1.0)"

OUT_DIR.mkdir(parents=True, exist_ok=True)
IM_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})

def can_fetch(url, ua="*"):
    robots_url = urljoin(BASE, "/robots.txt")
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(ua, url)
    except Exception:
        # fallback: unknown; return True but warn
        print("[warning] robots.txt could not be read; please check manually:", robots_url)
        return True

def load_soup_from_local_or_web(listing_url=LISTING, local_path=LOCAL_SOURCE):
    """Prefer local saved HTML if present (useful for debugging), else fetch from web."""
    if os.path.exists(local_path):
        print("[info] loading local saved HTML:", local_path)
        with open(local_path, "rb") as f:
            content = f.read()
        return BeautifulSoup(content, "lxml")
    else:
        print("[info] fetching listing page:", listing_url)
        r = session.get(listing_url, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")

def parse_listing(soup):
    """Parse the listing HTML and return list of article dicts with title, link, thumbnail, date (if available)."""
    articles = []
    # In the saved source, article tiles are inside divs with classes like 'col-md-6 lineg'
    # Each tile appears to have an <a href="..."> wrapping an <img class="img-fluid"> and then a div.card-body with <h3 class="newsch">title</h3> and a date string.
    tiles = soup.select("div.col-md-6.lineg")
    if not tiles:
        # fallback: try searching for anchors with /travel-tourism/ in href
        tiles = []
        for a in soup.find_all("a", href=True):
            if "/travel-tourism/" in a['href'] and a.find("img"):
                tiles.append(a.parent)  # best-effort
    for t in tiles:
        try:
            a = t.find("a", href=True)
            if not a:
                continue
            href = urljoin(BASE, a['href'])
            img_tag = a.find("img")
            thumb = urljoin(BASE, img_tag['src']) if img_tag and img_tag.get("src") else ""
            # title is in the sibling div.card-body -> h3.newsch
            title_tag = t.select_one("h3.newsch")
            title = title_tag.get_text(" ", strip=True) if title_tag else (a.get_text(" ", strip=True)[:150] if a else "")
            # date often appears just after the h3/newsch within the same 'date' anchor block or as text.
            date = ""
            # find the anchor with class 'date' inside tile
            date_anchor = t.find("a", class_="date")
            if date_anchor:
                # date text may be after the h3 or inside anchor text
                # remove the title from anchor text to get date
                raw = date_anchor.get_text(" ", strip=True)
                if title and title in raw:
                    date = raw.replace(title, "").strip()
                else:
                    # fallback: look for date-like substrings: e.g., 'Wednesday, 3 September 2025 00:10'
                    m = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday).+', raw)
                    date = m.group(0).strip() if m else raw.strip()
            else:
                # fallback: try find immediate text nodes containing weekday
                txt = t.get_text(" ", strip=True)
                m = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday).+', txt)
                if m:
                    date = m.group(0).strip()
            articles.append({
                "title": title,
                "listing_url": href,
                "thumbnail_url": thumb,
                "date": date
            })
        except Exception as e:
            print("[warn] parsing tile failed:", e)
    # dedupe by listing_url while preserving order
    seen = set()
    out = []
    for a in articles:
        if a['listing_url'] not in seen:
            seen.add(a['listing_url'])
            out.append(a)
    print(f"[info] found {len(out)} articles in listing")
    return out

def fetch_article_details(url):
    """Fetch article detail page and extract description/body and image URLs."""
    if not can_fetch(url):
        print("[robots] disallowed by robots.txt:", url)
        return {"description": "", "article_images": []}
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("[error] fetch failed:", url, e)
        return {"description": "", "article_images": []}

    soup = BeautifulSoup(r.text, "lxml")
    # Article body: many FT pages have article body in <div class="article-content"> or <div class="story-body">.
    body = ""
    # try a few selectors (robustness)
    for sel in ["div.article-content", "div.story-body", "div.article-body", "div#content", "div.entry-content"]:
        node = soup.select_one(sel)
        if node:
            body = node.get_text("\n\n", strip=True)
            break
    if not body:
        # fallback: take paragraphs under main container or first big text block
        paras = soup.find_all("p")
        if paras:
            body = "\n\n".join(p.get_text(" ", strip=True) for p in paras[:8])  # first few paragraphs
    # Collect images inside the article
    imgs = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src:
            imgs.append(urljoin(BASE, src))
    # dedupe
    imgs = list(dict.fromkeys(imgs))
    return {"description": body, "article_images": imgs}

def download_images(urls, title_prefix="", max_per_item=5):
    files = []
    for idx, url in enumerate(urls[:max_per_item]):
        try:
            parsed = urlparse(url)
            ext = os.path.splitext(parsed.path)[1] or ".jpg"
            safe_name = re.sub(r'[^A-Za-z0-9_\-\.]', '_', title_prefix)[:120]
            fname = f"{safe_name}_{idx}{ext}"
            outp = IM_DIR / fname
            if not outp.exists():
                r = session.get(url, stream=True, timeout=30)
                r.raise_for_status()
                with open(outp, "wb") as fh:
                    for chunk in r.iter_content(1024 * 32):
                        if chunk:
                            fh.write(chunk)
                time.sleep(random.uniform(0.2, 0.7))
            files.append(str(outp))
        except Exception as e:
            print("[warn] image download failed:", url, e)
    return files

def main(limit=None, download_images_flag=True):
    # polite robots check for listing
    if not can_fetch(LISTING):
        print("[error] robots.txt disallows scraping the listing. Aborting.")
        return

    soup = load_soup_from_local_or_web()
    listing = parse_listing(soup)

    if limit:
        listing = listing[:limit]

    rows = []
    for item in tqdm(listing, desc="articles"):
        details = fetch_article_details(item["listing_url"])
        # optionally download images (thumbnails + article images)
        downloaded = []
        if download_images_flag:
            to_dl = []
            if item.get("thumbnail_url"):
                to_dl.append(item["thumbnail_url"])
            to_dl.extend(details.get("article_images", []))
            downloaded = download_images(to_dl, title_prefix=item.get("title","").replace(" ","_")[:80], max_per_item=6)
        rows.append({
            "title": item.get("title",""),
            "date": item.get("date",""),
            "listing_url": item.get("listing_url",""),
            "thumbnail_url": item.get("thumbnail_url",""),
            "description": details.get("description",""),
            "article_image_urls": " | ".join(details.get("article_images", [])),
            "image_files": " | ".join(downloaded)
        })
        time.sleep(random.uniform(0.8, 1.6))
    # Save CSV
    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False)
    print("[ok] saved csv to:", CSV_PATH)

if __name__ == "__main__":
    # set limit=None to process all found articles, or a small number for testing
    main(limit=None, download_images_flag=True)
