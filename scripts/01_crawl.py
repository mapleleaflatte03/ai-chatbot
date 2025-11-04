import argparse, time, csv, re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import urllib.robotparser as urobot

HEADERS = {"User-Agent": "AI-ChatBot/1.0 (+Research)"}
REMOVE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"}
NAV_PATTERNS = [
    r"Trang chủ", r"Giới thiệu", r"Sản phẩm", r"Liên hệ", r"Tin tức",
    r"Call Now", r"Email", r"Xem thêm", r"Tháng \d+", r"\d+ comments",
    r"Category", r"Tags:", r"Share", r"Follow", r"Subscribe"
]


def load_robot(base):
    try:
        rp = urobot.RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        rp.read()
        return rp
    except Exception:
        return None


def extract_main_content(soup):
    # try to find main content area
    main = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|post|article|entry', re.I))
    
    if main:
        return main
    
    # if not found, find div with most text
    candidates = []
    for div in soup.find_all('div'):
        text = div.get_text(strip=True)
        tag_count = len(div.find_all())
        if tag_count > 0:
            density = len(text) / tag_count
            if density > 15 and len(text) > 150:
                candidates.append((density, len(text), div))
    
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][2]
    
    return soup


def clean_text(soup):
    # remove unwanted tags
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()
    
    # find main content
    main_content = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|post|entry', re.I))
    
    if not main_content:
        main_content = soup
    
    paragraphs = []
    for tag in main_content.find_all(['p', 'li', 'h1', 'h2', 'h3', 'td']):
        text = tag.get_text(" ", strip=True)
        if len(text) >= 30:
            paragraphs.append(text)
    
    # fallback if nothing found
    if not paragraphs:
        text = main_content.get_text(" ", strip=True)
    else:
        seen = set()
        unique = []
        for p in paragraphs:
            key = p[:40].lower()
            if key not in seen:
                seen.add(key)
                unique.append(p)
        text = " ".join(unique)
    
    text = re.sub(r"\s+", " ", text)
    
    return text.strip()


def crawl(seeds, limit, out):
    seen, queue = set(), list(seeds)
    allow_domains = {urlparse(s).netloc for s in seeds}
    robots = {d: load_robot(f"https://{d}") for d in allow_domains}

    rows = []
    while queue and len(rows) < limit:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        netloc = urlparse(url).netloc
        rp = robots.get(netloc)
        if rp and not rp.can_fetch(HEADERS["User-Agent"], url):
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            title = (soup.title.string.strip() if soup.title and soup.title.string else url)
            body = clean_text(soup)
            
            # quality check
            if len(body) < 100:
                continue
            
            words = body.split()
            if len(words) < 15:
                continue
            
            # get tags from headers
            tags = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2"])[:3] if h.get_text(strip=True)]
            
            rows.append({"url": url, "title": title, "body": body, "tags": ", ".join(tags)})

            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split("#")[0]
                parsed = urlparse(href)
                if parsed.netloc in allow_domains and parsed.scheme in {"http", "https"}:
                    if href not in seen and len(rows) + len(queue) < limit * 3:
                        queue.append(href)
            time.sleep(1.0)
        except Exception:
            continue

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "title", "body", "tags"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} pages -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", required=True, help="Comma-separated seed URLs")
    ap.add_argument("--out", default="data/faq.csv")
    ap.add_argument("--limit", type=int, default=80)
    args = ap.parse_args()
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    crawl(seeds, args.limit, args.out)
