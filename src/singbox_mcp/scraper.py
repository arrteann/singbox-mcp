"""Crawl and extract structured content from the official sing-box docs."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://sing-box.sagernet.org/configuration/"
DOMAIN = "sing-box.sagernet.org"
DEFAULT_DATA_FILE = Path(__file__).resolve().parents[2] / "data.json"

HEADERS = {
    "User-Agent": (
        "singbox-mcp-scraper/0.2 (+https://github.com/arrteann/singbox-mcp; docs indexing)"
    )
}

logger = logging.getLogger(__name__)


def get_links(url: str, soup: BeautifulSoup) -> list[str]:
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if not href or href.startswith("#"):
            continue

        full_url = urljoin(url, href)
        parsed = urlparse(full_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if parsed.netloc == DOMAIN and parsed.path.startswith("/configuration/"):
            links.append(clean_url)

    return links


def get_page(url: str) -> tuple[dict[str, Any] | None, BeautifulSoup | None]:
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        article = soup.find("article", class_="md-content__inner md-typeset")
        if not article:
            article = soup.find("main")

        if not article:
            logger.warning("No main content found for %s", url)
            return None, soup

        h1 = article.find("h1")
        title = h1.text.strip().replace("¶", "") if h1 else "No Title"

        content_blocks: list[dict[str, Any]] = []

        for anchor in article.find_all("a", class_="headerlink"):
            anchor.decompose()

        for tag in article.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "ul", "ol", "pre"]):
            if tag.name == "div":
                if "highlight" in tag.get("class", []):
                    code = tag.get_text(strip=True)
                    if code:
                        content_blocks.append({"type": "code", "text": code})
                continue

            if tag.name in ["ul", "ol"]:
                items = [li.get_text(strip=True) for li in tag.find_all("li", recursive=False)]
                if items:
                    content_blocks.append({"type": "list", "items": items})
                continue

            if tag.name == "pre":
                if not tag.find_parent("div", class_="highlight"):
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
                if tag.find_parent(["ul", "ol"]):
                    continue
                text = tag.get_text(strip=True)
                if text:
                    content_blocks.append({"type": "text", "text": text})

        return {"url": url, "title": title, "content": content_blocks}, soup
    except Exception as exc:  # noqa: BLE001 - crawl should continue on page failures
        logger.error("Error fetching %s: %s", url, exc)
        return None, None


def flatten_content(blocks: list[dict[str, Any]]) -> str:
    text_parts: list[str] = []

    for block in blocks:
        if block["type"] == "heading":
            level = int(block["level"][1])
            text_parts.append("\n" + ("#" * level) + " " + block["text"] + "\n")
        elif block["type"] == "text":
            text_parts.append(block["text"] + "\n")
        elif block["type"] == "code":
            text_parts.append("\n```\n" + block["text"] + "\n```\n")
        elif block["type"] == "list":
            for item in block["items"]:
                text_parts.append("- " + item + "\n")
            text_parts.append("\n")

    return "".join(text_parts).strip()


def build_data(base_url: str = BASE_URL, delay_seconds: float = 0.3) -> list[dict[str, str]]:
    visited: set[str] = set()
    to_visit: set[str] = {base_url}
    data: list[dict[str, str]] = []

    logger.info("Starting crawl from %s", base_url)
    while to_visit:
        url = to_visit.pop()
        if url in visited:
            continue

        logger.info("Scraping %s", url)
        page_data, soup = get_page(url)
        visited.add(url)

        if page_data:
            flat_text = flatten_content(page_data["content"])
            data.append(
                {
                    "url": page_data["url"],
                    "title": page_data["title"],
                    "content": flat_text,
                }
            )

        if soup:
            for link in get_links(url, soup):
                if link not in visited:
                    to_visit.add(link)

        time.sleep(delay_seconds)

    return data


def save_to_json(data: list[dict[str, str]], filename: str | Path = DEFAULT_DATA_FILE) -> Path:
    path = Path(filename)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    data = build_data()
    path = save_to_json(data)
    logger.info("Done. Scraped %s pages into %s", len(data), path)


if __name__ == "__main__":
    from .logging_config import setup_logging

    setup_logging()
    main()
