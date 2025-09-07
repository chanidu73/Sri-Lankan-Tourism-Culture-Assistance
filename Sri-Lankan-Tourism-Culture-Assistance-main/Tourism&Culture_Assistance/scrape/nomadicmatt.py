import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json

URL = "https://www.nomadicmatt.com/travel-blogs/sri-lanka-trip-planning-guide/"
USER_AGENT = "MyRAGScraper/1.0 (+mailto:animasha237@gmail.com)"
HEADERS = {
    "User-Agent": "MyRAGScraper/1.0 (+mailto:animasha237@gmail.com)"
}

def scrape_page(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Title
    title = soup.find("title").get_text(strip=True) if soup.title else ""

    # Article content (NomadicMatt uses div.entry-content for posts)
    article_div = soup.find("div", class_="entry-content")
    text = ""
    if article_div:
        # remove script/style
        for s in article_div(["script", "style"]):
            s.extract()
        text = article_div.get_text(separator=" ", strip=True)

    # Author
    author = ""
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta and author_meta.get("content"):
        author = author_meta["content"]

    # Publish date
    publish_date = ""
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        publish_date = time_tag["datetime"]

    # Images
    images = []
    if article_div:
        for img in article_div.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                images.append(urljoin(url, src))

    record = {
        "url": url,
        "title": title,
        "author": author,
        "publish_date": publish_date,
        "text_snippet": text[:10000],
        "images": images
    }
    return record

if __name__ == "__main__":
    data = scrape_page(URL)
    with open("nomadicmatt_srilanka.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[i] Scraped page saved to nomadicmatt_srilanka.json")
