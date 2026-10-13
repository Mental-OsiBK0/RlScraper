from rl_trade_scraper.scraper import clean, match_offers, parse_trade_count


def test_clean_collapses_newlines_and_spaces():
    assert clean("Titanium White\nOctane") == "Titanium White Octane"
    assert clean("Gold Nugget \n(Beta Reward) ") == "Gold Nugget (Beta Reward)"


def test_parse_trade_count_handles_one_and_many_digits():
    assert parse_trade_count("(7)") == 7
    assert parse_trade_count("(124)") == 124
    assert parse_trade_count("") == 0


def test_match_offers_splits_buy_and_sell():
    pairs = [
        ("Black\nDieci", "Titanium White\nOctane"),  # trader buys TW Octane
        ("Titanium White\nOctane", "1000 Credits"),   # trader sells TW Octane
        ("Black\nTunica", "Black\nDieci"),            # unrelated to Octane
    ]
    (octane,) = match_offers(pairs, ["titanium white octane"])
    assert octane.buy_offers == ["Black Dieci"]
    assert octane.sell_offers == ["1000 Credits"]


def test_match_offers_keeps_items_without_offers():
    results = match_offers([], ["Black Dieci", "black dieci", ""])
    assert len(results) == 1
    assert not results[0].has_offers
