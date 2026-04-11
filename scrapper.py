import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time

BASE_URL = "https://sing-box.sagernet.org/configuration/"
DOMAIN = "sing-box.sagernet.org"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_links(url, soup):
    links = []
    
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        
        # skip anchor links on the same page
        if href.startswith('#'):
            continue
            
        full_url = urljoin(url, href)
        parsed = urlparse(full_url)
        clean_url = parsed.scheme + "://" + parsed.netloc + parsed.path
        
        # Only keep links in the same domain and under /configuration/
        if parsed.netloc == DOMAIN and parsed.path.startswith('/configuration/'):
            links.append(clean_url)
            
    return links

def get_page(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Mkdocs-material main content inner
        article = soup.find("article", class_="md-content__inner md-typeset")
        if not article:
            article = soup.find("main")
            
        if not article:
            print(f"No main content found for {url}.")
            return None, soup
            
        h1 = article.find("h1")
        title = h1.text.strip().replace('¶', '') if h1 else "No Title"
        
        content_blocks = []
        
        # Removing anchor link markers usually added by mkdocs (headerlink)
        for anchor in article.find_all('a', class_='headerlink'):
            anchor.decompose()
            
        for tag in article.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "ul", "ol", "pre"]):
            # Divs commonly wrap code blocks in mkdocs (div.highlight > pre)
            if tag.name == "div":
                if 'highlight' in tag.get('class', []):
                    # It's a code block
                    code = tag.get_text(strip=True)
                    if code:
                        content_blocks.append({"type": "code", "text": code})
                continue
                
            if tag.name in ["ul", "ol"]:
                # Process list items
                items = []
                # Find all li. But nested lists shouldn't be duplicated if we use recursive=False
                for li in tag.find_all("li", recursive=False):
                    items.append(li.get_text(strip=True))
                if items:
                    content_blocks.append({"type": "list", "items": items})
                continue
                
            if tag.name == "pre":
                # Only process if not inside a div.highlight to avoid duplicate
                if not tag.find_parent('div', class_='highlight'):
                    code = tag.get_text(strip=True)
                    if code:
                        content_blocks.append({"type": "code", "text": code})
                continue
                
            if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                text = tag.get_text(strip=True)
                if text:
                    content_blocks.append({"type": "heading", "level": tag.name, "text": text})
                continue
                
            if tag.name == "p":
                # Paragraphs inside lists or other structures might be captured twice if we are not careful
                # Since we handle lists above, skip paragraphs inside them.
                if tag.find_parent(["ul", "ol"]):
                    continue
                text = tag.get_text(strip=True)
                if text:
                    content_blocks.append({"type": "text", "text": text})
                continue

        result = {
            "url": url,
            "title": title,
            "content": content_blocks
        }
        return result, soup
    except Exception as e:
        print(f"Error fetching the page {url}: {e}")
        return None, None

def flatten_content(blocks):
    text_parts = []

    for b in blocks:
        if b["type"] == "heading":
            level = int(b["level"][1])
            text_parts.append("\n" + ("#" * level) + " " + b["text"] + "\n")
        elif b["type"] == "text":
            text_parts.append(b["text"] + "\n")
        elif b["type"] == "code":
            text_parts.append("\n```\n" + b["text"] + "\n```\n")
        elif b["type"] == "list":
            for item in b["items"]:
                text_parts.append("- " + item + "\n")
            text_parts.append("\n")

    return "".join(text_parts).strip()

def build_data():
    visited = set()
    to_visit = {BASE_URL}
    
    data = []
    
    print(f"Starting crawl from {BASE_URL}")
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue
            
        print(f"Scraping: {url}")
        page_data, soup = get_page(url)
        visited.add(url)
        
        if page_data:
            flat_text = flatten_content(page_data["content"])
            data.append({
                "url": page_data["url"],
                "title": page_data["title"],
                "content": flat_text
            })
            
        if soup:
            new_links = get_links(url, soup)
            for link in new_links:
                if link not in visited:
                    to_visit.add(link)
                    
        time.sleep(0.3)
        
    return data

def save_to_json(data, filename="data.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    data = build_data()
    save_to_json(data)
    print(f"✅ Done! Scraped {len(data)} pages and saved to data.json")