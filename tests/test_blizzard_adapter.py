import json
from pathlib import Path

from wow_ah.adapters.blizzard_adapter import parse_commodities


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_commodities.json"


def test_parse_commodities():
    raw = json.loads(FIXTURE_PATH.read_text())
    listings = parse_commodities(raw)
    assert len(listings) == 6
    assert listings[0].item_id == 210796
    assert listings[0].unit_price == 15000
    assert listings[0].quantity == 200


def test_parse_commodities_empty():
    listings = parse_commodities({"auctions": []})
    assert listings == []


def test_parse_commodities_filter_by_watchlist():
    raw = json.loads(FIXTURE_PATH.read_text())
    listings = parse_commodities(raw, watchlist={210796})
    assert len(listings) == 3
    assert all(l.item_id == 210796 for l in listings)
