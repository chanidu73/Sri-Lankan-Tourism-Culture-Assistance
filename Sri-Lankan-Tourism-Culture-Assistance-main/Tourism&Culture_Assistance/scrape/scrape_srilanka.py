# scrape_srilanka.py
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import os
import tldextract
from urllib import robotparser
from collections import deque
from tqdm import tqdm

START_URL = "https://www.srilanka.travel/"
DOMAIN = urlparse(START_URL).netloc
SCHEME = urlparse(START_URL).scheme
USER_AGENT = "MyRAGScraper/1.0 (+mailto:animasha237@gmail.com)"
MAX_PAGES = 200         # change as needed
REQUEST_DELAY = 1.0     # seconds between requests (obey robots.txt crawl-delay if provided)
DOWNLOAD_IMAGES = True  # set False if you don't want image downloads
OUTPUT_JSONL = "results.jsonl"
IMAGES_DIR = "images"

# Ensure images dir exists
if DOWNLOAD_IMAGES:
    os.makedirs(IMAGES_DIR, exist_ok=True)

# Parse robots.txt
rp = robotparser.RobotFileParser()
robots_url = urljoin(START_URL, "/robots.txt")
rp.set_url(robots_url)
try:
    rp.read()
except Exception as e:
    print(f"[!] Warning: couldn't read robots.txt at {robots_url}: {e}")
    print("[!] Proceeding cautiously but you should check robots.txt manually.")
else:
    print(f"[i] Loaded robots.txt from {robots_url}")

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def allowed(url):
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        # If robots parser failed, default to False to be safe
        return False

def same_domain(url):
    return urlparse(url).netloc.endswith(tldextract.extract(START_URL).registered_domain)

def normalize_url(base, link):
    if not link:
        return None
    # Ignore javascript/mailto/tel fragments
    if link.startswith("javascript:") or link.startswith("mailto:") or link.startswith("tel:"):
        return None
    return urljoin(base, link.split('#')[0])

def extract_text(soup):
    # Remove scripts/styles and extract visible text
    for s in soup(["script", "style", "noscript", "iframe"]):
        s.extract()
    text = soup.get_text(separator=" ", strip=True)
    # collapse whitespace
    return " ".join(text.split())

def find_all_links(soup, base):
    links = set()
    for a in soup.find_all("a", href=True):
        u = normalize_url(base, a["href"])
        if u and same_domain(u):
            links.add(u)
    return links

def find_all_images(soup, base):
    imgs = set()
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        u = normalize_url(base, src)
        if u:
            imgs.add(u)
    return imgs

def download_image(url, save_dir=IMAGES_DIR):
    try:
        resp = session.get(url, stream=True, timeout=20)
        resp.raise_for_status()
        # derive filename
        parsed = urlparse(url)
        fname = os.path.basename(parsed.path) or ("img_" + str(abs(hash(url)))[:8])
        # avoid collisions
        out_path = os.path.join(save_dir, fname)
        base, ext = os.path.splitext(out_path)
        i = 1
        while os.path.exists(out_path):
            out_path = f"{base}_{i}{ext}"
            i += 1
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return out_path
    except Exception as e:
        print(f"[!] Failed to download image {url}: {e}")
        return None

def crawl(start_url):
    visited = set()
    q = deque([start_url])
    pages_crawled = 0

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as out_f:
        pbar = tqdm(total=MAX_PAGES, desc="Pages")
        while q and pages_crawled < MAX_PAGES:
            url = q.popleft()
            if url in visited:
                continue
            if not same_domain(url):
                continue
            if not allowed(url):
                print(f"[robots] Skipping disallowed URL: {url}")
                visited.add(url)
                continue

            try:
                resp = session.get(url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                print(f"[!] Error fetching {url}: {e}")
                visited.add(url)
                pbar.update(1)
                pages_crawled += 1
                time.sleep(REQUEST_DELAY)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            title_tag = soup.title.string.strip() if soup.title and soup.title.string else ""
            text = extract_text(soup)
            images = list(find_all_images(soup, url))
            links = find_all_links(soup, url)

            # Optionally download images
            downloaded = []
            if DOWNLOAD_IMAGES and images:
                for img_url in images:
                    if allowed(img_url):  # robots check for image URL too
                        saved = download_image(img_url)
                        if saved:
                            downloaded.append({"url": img_url, "saved_path": saved})
                    else:
                        print(f"[robots] image disallowed by robots.txt: {img_url}")

            record = {
                "url": url,
                "title": title_tag,
                "text_snippet": text[:10000],  # cap large output
                "all_images": images,
                "downloaded_images": downloaded,
                "outbound_links_count": len(links)
            }

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            # enqueue new links
            for link in links:
                if link not in visited:
                    q.append(link)

            visited.add(url)
            pages_crawled += 1
            pbar.update(1)

            # Respect politeness / crawl-delay
            try:
                crawl_delay = rp.crawl_delay(USER_AGENT)
                if crawl_delay:
                    time.sleep(crawl_delay)
                else:
                    time.sleep(REQUEST_DELAY)
            except Exception:
                time.sleep(REQUEST_DELAY)

        pbar.close()
    print(f"[i] Crawled {pages_crawled} pages. Output -> {OUTPUT_JSONL}")

if __name__ == "__main__":
    crawl(START_URL)
