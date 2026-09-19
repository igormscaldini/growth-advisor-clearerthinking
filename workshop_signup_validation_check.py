"""Drive the live Career Change Workshop sign-up form and check its email validation.

The sign-up form (GuidedTrack program 38791) validates the address in GuidedTrack code, and
that code can only be tested by running the real program: GuidedTrack has no offline runner,
and its semantics are what bite (an *if condition must test a variable, `text.find` returns
only the FIRST match). A September 2026 bug rejected every first.last@domain.com address for
three days because the check compared the first dot in the WHOLE address with the @ position.

Run this after any change to the program's email check:

    pip install playwright            # not a project dependency; uses the system Chrome
    python workshop_signup_validation_check.py

This is a manual tool, not part of pytest: it creates REAL runs. Every address that passes
validation gets a real confirmation email and a row in the sign-ups sheet, so the addresses
below are deliberately undeliverable (example.com is reserved by RFC 2606) or Igor's own.
Runs are tagged src=validationfixtest, which workshop_signups_sheet.py treats as a test
source, so the sheet sync never files them as sign-ups. Rows written live by the Vercel
route still need deleting by hand afterwards.
"""
from __future__ import annotations

import sys

RUN_URL = "https://www.guidedtrack.com/programs/gg4qpas/run?src=validationfixtest"
WARNING_TEXT = "doesn't look complete"

# (address, should be accepted, what it exercises)
CASES = [
    ("carlos.pruittjr@example.com", True, "dot in the local part (the Sep 2026 bug)"),
    ("first.last@sub.example.com", True, "dots in the local part and a multi-level domain"),
    ("jane@example.com", True, "plain address, no dot before the @"),
    ("igor.mscaldini+wsfixtest@gmail.com", True, "plus tag and a dotted local part"),
    ("nope@nope", False, "no dot in the domain"),
    ("@example.com", False, "nothing before the @"),
    ("jane doe@example.com", False, "space inside the address"),
    ("jane@doe@example.com", False, "two @ signs"),
    ("jane@example.c", False, "one-character TLD"),
    ("jane@.com", False, "domain starts with the dot"),
    ("jane@example.", False, "nothing after the dot"),
]


def run_case(browser, email: str, should_pass: bool) -> bool:
    """Submit one address; return True when the form accepted it."""
    page = browser.new_page(viewport={"width": 1100, "height": 1000})
    try:
        page.goto(RUN_URL, wait_until="networkidle")
        page.get_by_role("button", name="Sign up").first.click()
        page.wait_for_timeout(1200)
        page.fill("input[type=text]", email)
        page.get_by_role("button", name="Confirm sign up").first.click()
        if should_pass:
            # The confirmation page only renders after the email and the sheet service run.
            try:
                page.wait_for_selector("text=You're registered", timeout=30000)
                return True
            except Exception:
                return False
        page.wait_for_timeout(2500)
        return WARNING_TEXT not in page.inner_text("body")
    finally:
        page.close()


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is not installed: pip install playwright")

    failures = 0
    with sync_playwright() as p:
        # channel="chrome" is required: plain headless Chromium renders GuidedTrack blank.
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            for email, should_pass, why in CASES:
                accepted = run_case(browser, email, should_pass)
                ok = accepted == should_pass
                failures += 0 if ok else 1
                want = "accept" if should_pass else "reject"
                got = "accept" if accepted else "reject"
                print(f"{'OK  ' if ok else 'FAIL'} {email:36} want={want:6} got={got:6} ({why})")
        finally:
            browser.close()
    print("\nall cases behaved as expected" if not failures else f"\n{failures} case(s) wrong")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
