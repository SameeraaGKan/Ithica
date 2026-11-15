import json
from pathlib import Path

from app.services import oracle


def test_empty_reference_adds_nothing(monkeypatch, tmp_path: Path):
    f = tmp_path / "ref.json"
    f.write_text(json.dumps({"2013_rug_era": {"items": []}}))
    monkeypatch.setattr(oracle, "MERCH_REF_PATH", f)
    assert oracle.merch_reference_text() == ""


def test_filled_reference_lists_items_by_era(monkeypatch, tmp_path: Path):
    f = tmp_path / "ref.json"
    f.write_text(json.dumps({"_about": "x", "2013_rug_era": {"items": [
        {"name": "Rug hoodie", "year": 2013, "clue": "rug logo on chest"}]}}))
    monkeypatch.setattr(oracle, "MERCH_REF_PATH", f)
    text = oracle.merch_reference_text()
    assert "2013_rug_era: Rug hoodie (2013), clue: rug logo on chest" in text
