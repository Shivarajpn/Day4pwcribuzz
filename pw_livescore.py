"""
cricbuzz_score.py
Week 1 - Day 3 - Task 1: Capture a Live Cricket Score with Playwright

Flow:
  Chromium --> Cricbuzz live-scores page --> WAIT for match links
  --> group links into one CARD per match --> classify each card
      (LIVE / COMPLETED / UPCOMING) --> print the LIVE card
  --> score.png (the live card) + score_page.png (whole page)

Run headed (watch it work):   python cricbuzz_score.py
Run headless (no window):     python cricbuzz_score.py --headless
"""

import re
import sys
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# =====================================================================
# STEP 0 - Settings
# =====================================================================
URL = "https://www.cricbuzz.com/cricket-match/live-scores"

# Every match on Cricbuzz links to /live-cricket-scores/<matchId>/<name>
# Verify in Chrome console (F12):
#   document.querySelectorAll('a[href*="/live-cricket-scores/"]')
MATCH_SELECTOR = 'a[href*="/live-cricket-scores/"]'

WAIT_TIMEOUT_MS = 20_000
HEADLESS = "--headless" in sys.argv

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# ---- NEW: words that tell us the state of a match ----------------------
# A score: "287/4", "287-4"
SCORE_PATTERN = re.compile(r"\b\d{1,3}\s*[/-]\s*\d{1,2}\b")

# Match is over
COMPLETED_WORDS = [
    "won by", "won the", "match drawn", "match tied", "no result",
    "abandoned", "cancelled", "drawn",
]

# Match has not started
UPCOMING_WORDS = [
    "match starts", "starts at", "preview", "match yet to begin",
]

# Match is in progress (play going on, or paused mid-match)
LIVE_WORDS = [
    "need", "require", "trail by", "lead by", "opt to", "elected to",
    "innings break", "stumps", "lunch", "tea", "drinks", "rain",
    "delayed", "live", "day 1", "day 2", "day 3", "day 4", "day 5",
]


# =====================================================================
# Helper - tidy text
# =====================================================================
def clean_text(raw):
    lines = [line.strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line)


# =====================================================================
# NEW STEP - classify a card from its text
# =====================================================================
def classify(text):
    """Return 'COMPLETED', 'LIVE' or 'UPCOMING' for one match card."""
    t = text.lower()
    if any(word in t for word in COMPLETED_WORDS):
        return "COMPLETED"
    if SCORE_PATTERN.search(text):          # has a score and isn't finished
        return "LIVE"
    if any(word in t for word in LIVE_WORDS):   # e.g. toss done, rain delay
        return "LIVE"
    return "UPCOMING"


# =====================================================================
# NEW STEP - group links into one card per match
# =====================================================================
# One match card contains several links (team name, "Live Score",
# "Scorecard"...) that all point to the same matchId. Reading a single
# <a> often gives only "Live Score". This JavaScript runs inside the page:
# for each matchId it climbs up from the link to the BIGGEST parent that
# still holds links to only that one match -> that parent is the card.
# It tags each card with data-pw-card="<matchId>" so Python can find it.
MARK_CARDS_JS = """
(selector) => {
  const idOf = (a) => (a.getAttribute('href').match(/live-cricket-scores\\/(\\d+)/) || [])[1];
  const ids = [];
  for (const a of document.querySelectorAll(selector)) {
    const id = idOf(a);
    if (!id || ids.includes(id)) continue;
    let card = a;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      const parent = card.parentElement;
      const idsInside = new Set([...parent.querySelectorAll(selector)].map(idOf));
      if (idsInside.size > 1) break;          // parent holds another match -> stop
      card = parent;
    }
    card.setAttribute('data-pw-card', id);
    ids.push(id);
  }
  return ids;
}
"""


# =====================================================================
# STEP 1 - Open the browser and the page
# =====================================================================
def open_page(p):
    print(f"Launching Chromium ({'headless' if HEADLESS else 'headed'})...")
    browser = p.chromium.launch(headless=HEADLESS)
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1366, "height": 900},
    )
    page = context.new_page()
    print(f"Opening {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
    return browser, page


# =====================================================================
# STEP 2 - WAIT for match links (no fixed sleep)
# =====================================================================
def wait_for_matches(page):
    print("Waiting for matches to appear...")
    try:
        page.locator(MATCH_SELECTOR).first.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)
        return True
    except PlaywrightTimeout:
        return False


# =====================================================================
# STEP 3 - Build the cards and pick the LIVE one
# =====================================================================
def find_live_card(page):
    match_ids = page.evaluate(MARK_CARDS_JS, MATCH_SELECTOR)
    print(f"Found {len(match_ids)} matches on the page:\n")

    live_cards = []
    for match_id in match_ids[:20]:
        card = page.locator(f'[data-pw-card="{match_id}"]')
        text = clean_text(card.inner_text())
        status = classify(text)

        # Debug list - shows WHY each card was classified the way it was
        first_line = text.splitlines()[0] if text else "(empty)"
        print(f"  [{status:9}] {first_line[:70]}")

        if status == "LIVE":
            has_score = bool(SCORE_PATTERN.search(text))
            live_cards.append((has_score, card, text))

    # Prefer a live match that already has runs on the board
    live_cards.sort(key=lambda item: item[0], reverse=True)
    if live_cards:
        _, card, text = live_cards[0]
        return card, text
    return None, None


# =====================================================================
# Main
# =====================================================================
def main():
    print(f"Script started at: {datetime.now():%Y-%m-%d %H:%M:%S}")

    with sync_playwright() as p:
        browser, page = open_page(p)
        try:
            if not wait_for_matches(page):
                print("No matches found - page didn't load or the selector needs updating.")
                page.screenshot(path="score_page.png")
                print("saved score_page.png (for debugging)")
                return

            card, score_text = find_live_card(page)

            if card is None:
                print("\nNo live match right now - only completed/upcoming matches listed.")
                page.screenshot(path="score_page.png")
                print("saved score_page.png")
                return

            # STEP 4 - Print the live score
            print("\n===== LIVE SCORE =====")
            print(score_text)
            print("======================\n")

            # STEP 5 - Screenshots
            card.scroll_into_view_if_needed()
            card.screenshot(path="score.png")             # just the live card
            print("saved score.png")

            # Red outline around the live card for the full-page view
            card.evaluate("el => el.style.outline = '3px solid red'")
            page.screenshot(path="score_page.png")
            print("saved score_page.png")

        finally:
            browser.close()

    print(f"Script completed at: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()