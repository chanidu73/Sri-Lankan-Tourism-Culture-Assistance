#!/usr/bin/env python3
"""
scrape_srilanka.py

Scrapes srilanka.travel:
- Finds the main "story" sections (Wild, Heritage, Pristine, etc.)
- Crawls the Tourist Attractions listing (all pages)
- Scrapes each attraction detail: title, description, breadcrumbs/region, images,
  contact emails, phones, external links, source URL
- Downloads images to output/images/
- Saves master CSV and a summary PDF

Requirements:
pip install requests beautifulsoup4 pandas tqdm reportlab
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
from urllib.robotparser import RobotFileParser
import pandas as pd
import os, time, random, re
from tqdm import tqdm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

BASE = "https://www.srilanka.travel"
OUTPUT_DIR = "output"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
CSV_PATH = os.path.join(OUTPUT_DIR, "srilanka_attractions_full.csv")
PDF_PATH = os.path.join(OUTPUT_DIR, "srilanka_attractions_full.pdf")
USER_AGENT = "Mozilla/5.0 (compatible; srilanka-scraper/1.0)"

os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})

def get_soup(url, timeout=20):
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def safe_filename(s):
    s = unquote(s)
    s = re.sub(r'[:\\/*?"<>|]', '_', s)
    s = re.sub(r'\s+', '_', s).strip('_')
    return s[:180] if s else "file"

def can_fetch_url(url_to_check, ua="*"):
    robots_url = urljoin(BASE, "/robots.txt")
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(ua, url_to_check)
    except Exception:
        # Couldn't fetch robots.txt — warn and return True so user can decide
        print("[warning] couldn't read robots.txt — please check it manually:", robots_url)
        return True

def find_category_links():
    """Find category links from homepage (Wild, Heritage, Pristine, Bliss, Scenic, Thrills, Festive, Essence)."""
    categories = ["Wild", "Pristine", "Bliss", "Scenic", "Thrills", "Festive", "Heritage", "Essence"]
    soup = get_soup(BASE)
    found = {}
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True).lower()
        for cat in categories:
            if cat.lower() in text and cat not in found:
                found[cat] = urljoin(BASE, a['href'])
    return found

def find_attractions_listing():
    """Find the 'attractions' listing link on homepage (fallback to /tourist-attractions)."""
    soup = get_soup(BASE)
    for a in soup.find_all("a", href=True):
        href = a['href'].lower()
        if "attract" in href:
            return urljoin(BASE, a['href'])
    # fallback
    return urljoin(BASE, "/tourist-attractions")

def get_total_pages(listing_url):
    """Try to detect page count from pagination links on the listing page."""
    soup = get_soup(listing_url)
    nums = []
    for a in soup.find_all("a"):
        t = a.get_text(strip=True)
        if t.isdigit():
            try:
                nums.append(int(t))
            except: pass
    return max(nums) if nums else 1

def collect_attraction_links(listing_url, max_pages=None):
    """Crawl each listing page and collect 'view more' links to attractions."""
    base = listing_url.split('?')[0]
    total = get_total_pages(listing_url)
    if max_pages:
        total = min(total, max_pages)
    print(f"[info] detected {total} listing pages (will crawl 1..{total})")
    links = []
    for p in range(1, total+1):
        if p == 1:
            page_url = base
        else:
            page_url = f"{base}?page={p}"
        if not can_fetch_url(page_url):
            print(f"[robots] disallowed page: {page_url} — skipping")
            continue
        soup = get_soup(page_url)
        # find anchors with "view more" text (case-insensitive)
        for a in soup.find_all("a", string=re.compile(r"view\s*more", re.I)):
            href = a.get("href")
            if href:
                links.append(urljoin(BASE, href))
        # some links may be on the tile (title links) - also inspect tiles
        for tile in soup.select("a[href*='attraction']"):
            links.append(urljoin(BASE, tile.get("href")))
        time.sleep(random.uniform(0.8, 1.6))
    # dedupe while preserving order
    seen = set()
    out = []
    for l in links:
        if l not in seen:
            seen.add(l)
            out.append(l)
    print(f"[info] collected {len(out)} attraction links (deduped)")
    return out

def parse_attraction_page(url, download_images=True, max_images_per_attraction=3):
    """Parse an attraction detail page and optionally download images."""
    if not can_fetch_url(url):
        print("[robots] page disallowed by robots.txt:", url)
        return None
    try:
        soup = get_soup(url)
    except Exception as e:
        print("[error] could not fetch:", url, e)
        return None

    # Title: prefer H1/H2 near top
    title_tag = soup.find(["h1", "h2"])
    title = title_tag.get_text(" ", strip=True) if title_tag else (soup.title.string.strip() if soup.title else "")

    # Breadcrumbs / region: often available as the first line / breadcrumb area
    breadcrumb = ""
    # try finding a breadcrumb-like container
    bc = soup.find(lambda tag: tag.name in ("div", "p") and '|' in tag.get_text() and len(tag.get_text())<200)
    if bc:
        breadcrumb = bc.get_text(" ", strip=True)
    else:
        # fallback: split title by '|' if present
        if title and '|' in title:
            parts = [p.strip() for p in title.split('|')]
            if len(parts) > 1:
                breadcrumb = parts[0]

    # Description: join paragraphs that follow the main title until 'Photos' or 'Video' or 'Nearby' headings
    description_parts = []
    stop_keywords = ['photos', 'video', 'nearby', 'places to stay', 'more', 'hide']
    if title_tag:
        for sib in title_tag.find_next_siblings():
            if sib.name and sib.name.startswith('h'):
                txt = sib.get_text(" ", strip=True).lower()
                if any(k in txt for k in stop_keywords):
                    break
            # add text blocks (paragraphs and divs)
            if sib.name in ('p', 'div'):
                text = sib.get_text(" ", strip=True)
                if text:
                    description_parts.append(text)
    description = "\n\n".join(description_parts).strip()

    # Images: collect img[src] and data-src in the page (limit to few)
    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        src = urljoin(BASE, src)
        # normalize
        if src not in images:
            images.append(src)
    # try also links in a "Photos" section (some sites wrap images in anchors)
    for a in soup.find_all("a", href=True):
        href = a['href']
        if href.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
            u = urljoin(BASE, href)
            if u not in images:
                images.append(u)

    # Contact-like info: emails and phone numbers by regex
    page_text = soup.get_text(" ", strip=True)
    emails = list(dict.fromkeys(re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', page_text)))
    phones = list(dict.fromkeys(re.findall(r'\+?\d[\d\-\s().]{6,}\d', page_text)))

    # External URLs found on the page
    external_urls = []
    for a in soup.find_all("a", href=True):
        href = a['href']
        if href.startswith("http") and BASE not in href:
            if href not in external_urls:
                external_urls.append(href)

    # Download images (optionally) - limit number per attraction to avoid huge downloads
    downloaded = []
    if download_images:
        for idx, img_url in enumerate(images[:max_images_per_attraction]):
            try:
                ext = os.path.splitext(urlparse(img_url).path)[1] or ".jpg"
                fname = safe_filename(f"{title}_{idx}") + ext
                outpath = os.path.join(IMAGES_DIR, fname)
                # skip if already exists
                if not os.path.exists(outpath):
                    r = session.get(img_url, stream=True, timeout=20)
                    r.raise_for_status()
                    with open(outpath, "wb") as fh:
                        for chunk in r.iter_content(1024 * 32):
                            if chunk:
                                fh.write(chunk)
                    time.sleep(random.uniform(0.2, 0.8))
                downloaded.append(outpath)
            except Exception as ex:
                print("[warn] failed to download image:", img_url, ex)
    # Return a dict
    return {
        "source_url": url,
        "title": title,
        "breadcrumb": breadcrumb,
        "description": description,
        "image_urls": images,
        "image_files": downloaded,
        "emails": emails,
        "phones": phones,
        "external_urls": external_urls,
    }

def build_pdf(data_rows, pdf_path=PDF_PATH):
    """Create a simple PDF summary (one attraction per page-ish)."""
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    for item in data_rows:
        story.append(Paragraph(item.get("title", "Untitled"), styles["Heading2"]))
        if item.get("breadcrumb"):
            story.append(Paragraph(f"<i>{item.get('breadcrumb')}</i>", styles["Normal"]))
        story.append(Spacer(1, 6))
        desc = item.get("description", "")
        if desc:
            # trim long descriptions for readability (or change as you prefer)
            story.append(Paragraph(desc.replace("\n","<br/>"), styles["BodyText"]))
            story.append(Spacer(1, 6))
        # first downloaded image (if any)
        imgs = item.get("image_files", [])
        if imgs:
            try:
                img_path = imgs[0]
                # scale image to fit width
                img = RLImage(img_path)
                img.drawHeight = 150
                img.drawWidth = 250
                story.append(img)
                story.append(Spacer(1, 6))
            except Exception as e:
                print("[warn] could not add image to PDF:", e)
        # contacts
        if item.get("emails"):
            story.append(Paragraph("Emails: " + ", ".join(item["emails"]), styles["Normal"]))
        if item.get("phones"):
            story.append(Paragraph("Phones: " + ", ".join(item["phones"]), styles["Normal"]))
        # source
        story.append(Paragraph(f"Source: {item.get('source_url')}", styles["Normal"]))
        story.append(Spacer(1, 12))
    doc.build(story)
    print(f"[ok] pdf saved to: {pdf_path}")

def main():
    print("[start] scraping srilanka.travel")
    # Find categories (Wild, Heritage, ...)
    cats = find_category_links()
    print("[info] found category links:", cats)

    # Attractions listing
    listing = find_attractions_listing()
    print("[info] attractions listing:", listing)

    # Check robots for listing
    if not can_fetch_url(listing):
        print("[error] robots.txt disallows scraping the attractions listing. Aborting.")
        return

    # Collect attraction links
    attraction_links = collect_attraction_links(listing)

    # OPTIONAL: limit for testing - set to None to crawl all
    # For large runs, remove the limit. For now we set None.
    LIMIT = None  # e.g., 50 to limit
    if LIMIT:
        attraction_links = attraction_links[:LIMIT]

    results = []
    for link in tqdm(attraction_links, desc="attractions"):
        item = parse_attraction_page(link, download_images=True, max_images_per_attraction=2)
        if item:
            results.append(item)
        # polite delay
        time.sleep(random.uniform(0.9, 1.8))

    # Save CSV
    if results:
        # normalize lists into strings for CSV
        df = pd.DataFrame(results)
        df['image_urls'] = df['image_urls'].apply(lambda x: " | ".join(x) if isinstance(x, list) else "")
        df['image_files'] = df['image_files'].apply(lambda x: " | ".join(x) if isinstance(x, list) else "")
        df['emails'] = df['emails'].apply(lambda x: " | ".join(x) if isinstance(x, list) else "")
        df['phones'] = df['phones'].apply(lambda x: " | ".join(x) if isinstance(x, list) else "")
        df['external_urls'] = df['external_urls'].apply(lambda x: " | ".join(x) if isinstance(x, list) else "")
        df.to_csv(CSV_PATH, index=False)
        print(f"[ok] csv saved to: {CSV_PATH}")

        # Build PDF summary
        build_pdf(results, PDF_PATH)
    else:
        print("[warn] no results collected.")

if __name__ == "__main__":
    main()
