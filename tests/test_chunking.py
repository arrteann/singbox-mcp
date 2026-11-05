from singbox_mcp.rag import chunk_document, reciprocal_rank_fusion, tokenize


def test_chunk_document_splits_on_headings():
    content = """# Intro

Welcome.

## Inbound

Sniffing options live here.

### Sniff

Enable protocol sniffing.

## Outbound

Direct outbound.
"""
    chunks = chunk_document(content, url="https://example.com/x", title="Config")
    assert len(chunks) >= 3
    assert any("Inbound" in c["heading_path"] for c in chunks)
    assert any("Sniff" in c["heading_path"] for c in chunks)
    assert all(c["text"].startswith("[Config]") for c in chunks)


def test_tokenize_and_rrf():
    tokens = tokenize("Enable sniffing / inbound")
    assert "sniffing" in tokens
    assert "inbound" in tokens
    assert "/" not in tokens
    fused = reciprocal_rank_fusion([[0, 1, 2], [1, 0, 3]])
    assert fused[1] > fused[2]
    assert 0 in fused and 3 in fused
