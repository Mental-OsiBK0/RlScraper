"""Core scraping logic for collecting Rocket League trade offers.

The scraper opens a player's public trade page on rocket-league.com, walks
through every trade post and records which offers involve the items you are
interested in.

Terminology used throughout the module:

* **has**   - the items a trader is offering in a post (left column).
* **wants** - the items the trader asks for in return (right column).

Items in the two columns are paired by position, so slot ``n`` on the
"has" side is traded for slot ``n`` on the "wants" side.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional, Sequence, Tuple
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

PLAYER_URL = "https://rocket-league.com/player/{username}/"

#: High-value items checked by the "popular items" scan.
DEFAULT_ITEMS: Tuple[str, ...] = (
    "Titanium White Octane",
    "Titanium White Fennec",
    "Titanium White Dingo",
    "Titanium White Zomba",
    "Titanium White Emerald",
    "Titanium White Dieci",
    "Black Dieci",
    "Titanium White Draco",
    "Gold Nugget (Beta Reward)",
    "Titanium White Helios",
    "Titanium White Dominus",
    "Black Tunica",
    "Black Alchemist",
    "Black Sunburst",
    "Titanium White Reaper",
    "Titanium White Dueling Dragons",
    "Titanium White Octane Striker",
)

MAX_SLOTS_PER_SIDE = 10
HAS_SIDE = 1
WANTS_SIDE = 3
# Depending on the profile layout the trade list lives in one of these sections.
CANDIDATE_SECTIONS = (2, 3)

_SECTION_XPATH = "/html/body/main/section/div/div[3]/div[{section}]"
_TRADE_COUNT_XPATH = _SECTION_XPATH + "/div/div[2]/h1/span"
_SLOT_XPATH = (
    _SECTION_XPATH
    + "/div/div[3]/div[{post}]/div[1]/div[2]/div[{side}]/div[{slot}]"
)
_PRIVACY_BUTTON_ID = "acceptPrivacyPolicy"


class ScraperError(RuntimeError):
    """Raised when the trade page cannot be loaded or parsed."""


@dataclass
class ItemOffers:
    """All offers found for a single item."""

    name: str
    #: Trader wants this item and offers these items for it.
    buy_offers: list = field(default_factory=list)
    #: Trader has this item and asks for these items in return.
    sell_offers: list = field(default_factory=list)

    @property
    def has_offers(self) -> bool:
        return bool(self.buy_offers or self.sell_offers)

    def summary(self) -> str:
        buying = ", ".join(self.buy_offers) or "none"
        selling = ", ".join(self.sell_offers) or "none"
        return (
            f"{self.name}\n"
            f"  Buying  (trader offers): {buying}\n"
            f"  Selling (trader asks):   {selling}"
        )


def clean(text: str) -> str:
    """Collapse line breaks and repeated whitespace into single spaces."""
    return " ".join(text.split())


def normalize(text: str) -> str:
    """Return a whitespace- and case-insensitive key for comparing item names."""
    return clean(text).casefold()


def parse_trade_count(text: str) -> int:
    """Extract the number of trades from a heading such as ``"(12)"``."""
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def match_offers(
    pairs: Iterable[Tuple[str, str]], item_names: Sequence[str]
) -> list:
    """Group ``(has, wants)`` trade pairs by the requested item names.

    Returns one :class:`ItemOffers` per unique requested item, in the order
    the items were requested.
    """
    results = {}
    for name in item_names:
        key = normalize(name)
        if key and key not in results:
            results[key] = ItemOffers(clean(name))

    for has, wants in pairs:
        has_key, wants_key = normalize(has), normalize(wants)
        if wants_key in results:
            results[wants_key].buy_offers.append(clean(has))
        if has_key in results:
            results[has_key].sell_offers.append(clean(wants))

    return list(results.values())


class TradeScraper:
    """Selenium-based scraper. Use it as a context manager::

        with TradeScraper() as scraper:
            offers = scraper.scrape("some_player", DEFAULT_ITEMS)
    """

    def __init__(self, headless: bool = True, timeout: float = 10.0) -> None:
        self.headless = headless
        self.timeout = timeout
        self._driver: Optional[WebDriver] = None

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "TradeScraper":
        self._driver = self._create_driver()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            finally:
                self._driver = None

    def _create_driver(self) -> WebDriver:
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
        try:
            # Selenium >= 4.6 downloads a matching chromedriver automatically.
            return webdriver.Chrome(options=options)
        except WebDriverException as exc:
            raise ScraperError(f"Could not start Chrome: {exc.msg}") from exc

    @property
    def driver(self) -> WebDriver:
        if self._driver is None:
            raise ScraperError("Scraper is not running; use it as a context manager.")
        return self._driver

    # -- public API --------------------------------------------------------

    def scrape(self, username: str, item_names: Sequence[str]) -> list:
        """Collect offers from ``username``'s trades for each of ``item_names``."""
        username = username.strip()
        if not username:
            raise ValueError("Username must not be empty.")
        if not item_names:
            raise ValueError("At least one item name is required.")

        self._open_player_page(username)
        section, count = self._find_trade_section()
        return match_offers(self._iter_trade_pairs(section, count), item_names)

    # -- page helpers ------------------------------------------------------

    def _open_player_page(self, username: str) -> None:
        url = PLAYER_URL.format(username=quote(username, safe=""))
        try:
            self.driver.get(url)
        except WebDriverException as exc:
            raise ScraperError(f"Could not load {url}: {exc.msg}") from exc
        self._accept_privacy_policy()

    def _accept_privacy_policy(self) -> None:
        try:
            button = WebDriverWait(self.driver, 3).until(
                EC.element_to_be_clickable((By.ID, _PRIVACY_BUTTON_ID))
            )
            button.click()
        except TimeoutException:
            pass  # The banner is not always shown.

    def _find_trade_section(self) -> Tuple[int, int]:
        def locate(driver: WebDriver):
            for section in CANDIDATE_SECTIONS:
                found = driver.find_elements(
                    By.XPATH, _TRADE_COUNT_XPATH.format(section=section)
                )
                if found:
                    return section, found[0].text
            return False

        try:
            section, text = WebDriverWait(self.driver, self.timeout).until(locate)
        except TimeoutException as exc:
            raise ScraperError(
                "No trade list found. The user may not exist, may have no "
                "active trades, or the site layout may have changed."
            ) from exc
        return section, parse_trade_count(text)

    def _iter_trade_pairs(self, section: int, count: int) -> Iterator[Tuple[str, str]]:
        for post in range(1, count + 1):
            for slot in range(1, MAX_SLOTS_PER_SIDE + 1):
                has = self._slot_text(section, post, HAS_SIDE, slot)
                wants = self._slot_text(section, post, WANTS_SIDE, slot)
                if has is None or wants is None:
                    break
                yield has, wants

    def _slot_text(self, section: int, post: int, side: int, slot: int) -> Optional[str]:
        found = self.driver.find_elements(
            By.XPATH,
            _SLOT_XPATH.format(section=section, post=post, side=side, slot=slot),
        )
        return found[0].text if found else None
