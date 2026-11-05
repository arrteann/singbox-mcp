from bs4 import BeautifulSoup

from singbox_mcp.scraper import DOMAIN, flatten_content, get_links


def test_flatten_content_formats_blocks():
    text = flatten_content(
        [
            {"type": "heading", "level": "h2", "text": "Tun"},
            {"type": "text", "text": "Virtual network interface."},
            {"type": "code", "text": '{"type":"tun"}'},
            {"type": "list", "items": ["mtu", "auto_route"]},
        ]
    )
    assert "## Tun" in text
    assert "Virtual network interface." in text
    assert '```\n{"type":"tun"}\n```' in text
    assert "- mtu" in text
    assert "- auto_route" in text


def test_get_links_filters_domain_and_path():
    html = f"""
    <html><body>
      <a href="/configuration/inbound/">inbound</a>
      <a href="/configuration/outbound/#direct">outbound</a>
      <a href="#local">anchor</a>
      <a href="https://example.com/configuration/x">external</a>
      <a href="https://{DOMAIN}/manual/">manual</a>
    </body></html>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = get_links(f"https://{DOMAIN}/configuration/", soup)
    assert f"https://{DOMAIN}/configuration/inbound/" in links
    assert f"https://{DOMAIN}/configuration/outbound/" in links
    assert all("/manual/" not in link for link in links)
    assert all("example.com" not in link for link in links)
