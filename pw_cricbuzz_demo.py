"""
cricbuzz_score.py
Week 1 - Day 3 - Task 1: Capture a Live Cricket Score with Playwright

Flow:
  Chromium --> Cricbuzz live-scores page --> WAIT for match cards
  --> pick the first match that has a score --> print it --> score.png

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

# SELECTOR: every match card on Cricbuzz links to a page whose URL contains
# "/live-cricket-scores/". Matching on the link's href is more stable than
# matching on CSS class names, which change whenever the site is redesigned.
# >>> Verify it yourself: open the page in Chrome, press F12 -> Console, run:
#     document.querySelectorAll('a[href*="/live-cricket-scores/"]')
# If the site changes, update this one line.
MATCH_SELECTOR = 'a[href*="/live-cricket-scores/"]'

# A score looks like "287/4" or "287-4"
SCORE_PATTERN = re.compile(r"\d+\s*[/-]\s*\d+")

WAIT_TIMEOUT_MS = 20_000          # max wait for the cards: 20 seconds
HEADLESS = "--headless" in sys.argv

# A normal Chrome user-agent, so the site serves the same page in headless mode
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


# =====================================================================
# Helper - tidy up the card text
# =====================================================================
def clean_text(raw):
    """Remove blank lines and extra spaces from inner_text()."""
    lines = [line.strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line)


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
    # 'domcontentloaded' = the HTML has arrived. The score comes later via
    # JavaScript, which is why we wait for the element in Step 2.
    page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
    return browser, page


# =====================================================================
# STEP 2 - WAIT for the match cards (no fixed sleep)
# =====================================================================
def wait_for_matches(page):
    print("Waiting for match cards to appear...")
    cards = page.locator(MATCH_SELECTOR)
    try:
        # Returns as soon as the first card is visible, so 0.5s on a fast day
        # or 15s on a slow day; fails only after WAIT_TIMEOUT_MS
        cards.first.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)
    except PlaywrightTimeout:
        return None
    return cards


# =====================================================================
# STEP 3 - Pick the first match that actually has a score
# =====================================================================
def find_scored_match(cards):
    count = min(cards.count(), 15)          # check the first 15 cards
    for i in range(count):
        card = cards.nth(i)
        text = clean_text(card.inner_text())
        if SCORE_PATTERN.search(text):      # has "287/4"-style score?
            return card, text
    return None, None


# =====================================================================
# Main - run the steps in order
# =====================================================================
def main():
    print(f"Script started at: {datetime.now():%Y-%m-%d %H:%M:%S}")

    with sync_playwright() as p:
        browser, page = open_page(p)

        try:
            cards = wait_for_matches(page)
            if cards is None:
                print("No match cards found - the page did not load, or the selector needs updating.")
                page.screenshot(path="score.png")
                print("saved score.png (for debugging)")
                return

            card, score_text = find_scored_match(cards)

            if card is None:
                # The "no match live" case: report it instead of crashing
                print("No match in progress right now (only upcoming fixtures listed).")
            else:
                # STEP 4 - Print the score
                print("\n" + score_text + "\n")
                card.scroll_into_view_if_needed()

            # STEP 5 - Screenshot
            page.screenshot(path="score.png")
            print("saved score.png")

        finally:
            # STEP 6 - Always close the browser, even if something failed
            browser.close()

    print(f"Script completed at: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()