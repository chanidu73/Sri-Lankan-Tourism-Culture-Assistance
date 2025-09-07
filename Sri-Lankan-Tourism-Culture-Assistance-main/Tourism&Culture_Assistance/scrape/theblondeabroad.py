from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin

URL = "https://www.theblondeabroad.com/ultimate-sri-lanka-travel-guide/"

def scrape_with_playwright(url):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = soup.title.get_text(strip=True) if soup.title else ""

        # Article content
        main = soup.find("div", class_="entry-content")
        text = ""
        if main:
            for tag in main(["script", "style"]):
                tag.extract()
            text = main.get_text(separator=" ", strip=True)

        # Images
        images = []
        if main:
            for img in main.find_all("img"):
                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                if src:
                    images.append(urljoin(url, src))

        browser.close()

        return {
            "url": url,
            "title": title,
            "text_snippet": text[:10000],
            "images": images
        }

if __name__ == "__main__":
    data = scrape_with_playwright(URL)
    with open("blondeabroad_sri_lanka_playwright.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("[+] Data saved to blondeabroad_sri_lanka_playwright.json")
