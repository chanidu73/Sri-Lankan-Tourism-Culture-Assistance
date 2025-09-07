import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib import robotparser
import time, json, os
from collections import deque
import tldextract
from tqdm import tqdm

BASE_URL = "https://www.thecommonwanderer.com"
START_PAGES = [
    BASE_URL + "/blog/category/Sri+Lanka",
    BASE_URL + "/sri-lanka"
]
USER_AGENT = "MyRAGScraper/1.0 (+mailto:animasha237@gmail.com)"
MAX_PAGES = 100
REQUEST_DELAY = 1.0
OUTPUT_JSONL = "commonwanderer_sri_lanka.jsonl"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# robots.txt setup
rp = robotparser.RobotFileParser()
rp.set_url(urljoin(BASE_URL, "/robots.txt"))
rp.read()

def allowed(url):
    return rp.can_fetch(USER_AGENT, url)

def same_site(url):
    return tldextract.extract(url).registered_domain == tldextract.extract(BASE_URL).registered_domain

def normalize_link(base, link):
    if not link or link.startswith("javascript:") or link.startswith("mailto:"):
        return None
    return urljoin(base, link.split('#')[0])

def extract_text(soup):
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    return " ".join(soup.get_text(separator=" ", strip=True).split())

def extract_page(url):
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    dt = ""
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        dt = time_tag["datetime"]
    # main content region heuristics
    main = soup.find("div", class_="entry-content") or soup.find("main") or soup.body
    text = extract_text(main) if main else ""
    images = []
    if main:
        for img in main.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                images.append(urljoin(url, src))
    return {"url": url, "title": title, "publish_date": dt, "text": text[:20000], "images": images}

def crawl():
    visited = set()
    q = deque(START_PAGES)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as fout:
        pbar = tqdm(total=MAX_PAGES, desc="Crawling pages")
        while q and len(visited) < MAX_PAGES:
            url = q.popleft()
            if url in visited or not same_site(url) or not allowed(url):
                visited.add(url)
                continue
            try:
                record = extract_page(url)
            except Exception as e:
                print(f"[!] Error at {url}: {e}")
                visited.add(url)
                pbar.update(1)
                continue

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            fout.flush()
            visited.add(url)
            pbar.update(1)

            # enqueue links
            soup = BeautifulSoup(requests.get(url, headers={"User-Agent":USER_AGENT}).text, "html.parser")
            for a in soup.find_all("a", href=True):
                link = normalize_link(url, a["href"])
                if link and link not in visited and same_site(link):
                    q.append(link)

            time.sleep(REQUEST_DELAY)
        pbar.close()
    print(f"[+] Done. Scraped {len(visited)} pages -> {OUTPUT_JSONL}")

if __name__ == "__main__":
    crawl()
