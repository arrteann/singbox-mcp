from singbox_mcp.rag import RAGSystem


def _chunk(text: str, title: str, section: str) -> dict:
    return {
        "text": text,
        "url": f"https://example.com/{title.lower()}",
        "title": title,
        "section": section,
        "heading_path": f"{title} > {section}",
        "chunk_index": 0,
    }


def test_keyword_search_ranks_relevant_chunk():
    system = RAGSystem()
    system.metadata = [
        _chunk("Configure DNS servers and strategy.", "DNS", "server"),
        _chunk("Enable protocol sniffing on inbound connections.", "Inbound", "sniff"),
        _chunk("Set MTU for the tun interface.", "Tun", "mtu"),
    ]
    system._rebuild_bm25()

    results = system.search("inbound sniffing", top_k=2, mode="keyword")
    assert results
    assert results[0]["meta"]["title"] == "Inbound"
    assert results[0]["scores"]["bm25"] == 1.0
    assert "error" not in results[0]
