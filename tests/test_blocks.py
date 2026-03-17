from triageflow.document_blocks import join_blocks, split_blocks


def test_split_blocks_basic():
    text = """# Header

H001 (Status: Open | Confidence: Medium)
Hypothesis: a

H002 (Status: Open | Confidence: Low)
Hypothesis: b
"""
    blocks = split_blocks(text, r"^H\d{3}\b.*")
    assert len(blocks) == 2
    assert blocks[0][0].startswith("H001")
    assert blocks[1][0].startswith("H002")


def test_join_blocks_round_trip_keeps_headers():
    blocks = [["H001 (Status: Open)", "line1"], ["H002 (Status: Closed)", "line2"]]
    out = join_blocks(blocks)
    assert "H001" in out
    assert "H002" in out
