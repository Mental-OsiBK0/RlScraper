# Rocket League Trade Scraper

A desktop tool that reads a player's public trade posts on
[rocket-league.com](https://rocket-league.com) and shows which offers involve
the items you care about: what the trader **gives** for an item and what they
**ask** for it.

Built with **Python**, **PyQt5** (GUI) and **Selenium** (browser automation).

## Features

- **Popular items scan** – checks a player's trades for 17 high-value items
  (Titanium White Octane, Black Dieci, Gold Nugget, …).
- **Custom item search** – look up any item by color and name.
- Case- and whitespace-insensitive item matching.
- Scraping runs on a background thread, so the window never freezes.
- Optional headless mode (no visible browser window).
- Clear error messages for missing users, empty trade lists or layout changes.

## How it works

Each trade post on rocket-league.com has two columns, "has" and "wants", whose
slots are paired by position. The scraper walks every post and slot and,
for each item you selected, records:

| Result  | Meaning                                                        |
|---------|----------------------------------------------------------------|
| Buying  | The trader wants the item and offers *these items* for it.     |
| Selling | The trader has the item and asks for *these items* in return.  |

## Getting started

Requirements: Python 3.8+ and Google Chrome. Selenium 4.6+ downloads a
matching ChromeDriver automatically.

```bash
git clone https://github.com/<your-username>/rl-trade-scraper.git
cd rl-trade-scraper
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py                   # or: python -m rl_trade_scraper
```

## Using it from code

```python
from rl_trade_scraper import DEFAULT_ITEMS, TradeScraper

with TradeScraper(headless=True) as scraper:
    for offer in scraper.scrape("some_player", DEFAULT_ITEMS):
        if offer.has_offers:
            print(offer.summary())
```

## Project structure

```
rl-trade-scraper/
├── main.py                    # Entry point
├── rl_trade_scraper/
│   ├── scraper.py             # Selenium scraping + offer matching
│   └── gui.py                 # PyQt5 interface
├── tests/
│   └── test_parsing.py        # Unit tests for parsing/matching logic
├── requirements.txt
└── requirements-dev.txt
```

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Notes

- The scraper relies on the current page structure of rocket-league.com. If
  the site layout changes, the XPath selectors in `scraper.py` may need to be
  updated.
- Please use responsibly and respect the website's terms of service.
- This project is not affiliated with Psyonix or rocket-league.com.

## License

MIT
