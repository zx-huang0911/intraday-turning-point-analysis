"""Optional browser check: pip install playwright, then supply an installed Chrome.

Usage: python scripts/check_report.py examples/report/index.html \
  --browser /usr/bin/google-chrome --out .local/browser-check
Only use the synthetic demo; output screenshots contain report data.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--browser", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.browser, headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda req: (
                external.append(req.url) if req.url.startswith(("https://", "http://")) else None
            ),
        )
        page.goto(args.report.resolve().as_uri())
        assert page.locator("#kind").inner_text() == "合成数据 · DEMO"
        page.screenshot(path=str(args.out / "desktop.png"), full_page=True)
        page.get_by_role("tab", name="案例与逐日得分").click()
        page.locator("#symbol").select_option("DEMO_B")
        assert "DEMO_B" in page.locator("#case-title").inner_text()
        page.locator("#price-chart").hover()
        assert "close:" in page.locator("#hover-price").inner_text()
        page.screenshot(path=str(args.out / "explorer.png"), full_page=True)
        page.get_by_role("tab", name="方法与溯源").click()
        assert page.locator("#quality-rows tr").count() == 2
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("tab", name="研究概览").click()
        assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        page.screenshot(path=str(args.out / "mobile.png"), full_page=True)
        # Keyboard navigation and every visible local download target.
        page.get_by_role("tab", name="研究概览").focus()
        page.keyboard.press("ArrowRight")
        assert page.locator("#tab-explorer").get_attribute("aria-selected") == "true"
        for link in page.locator("a[download]").all():
            if link.is_visible():
                assert (args.report.parent / link.get_attribute("href")).is_file()
        assert not errors, errors
        assert not external, external
        evidence = {
            "browser": browser.version,
            "desktop": "1440x1100",
            "mobile": "390x844",
            "checks": [
                "tabs",
                "symbol selection",
                "hover",
                "quality table",
                "mobile overflow",
                "keyboard tabs",
                "visible downloads",
                "offline assets",
            ],
            "errors": errors,
            "external_requests": external,
        }
        (args.out / "browser-check.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
        browser.close()
        print("Browser checks passed")


if __name__ == "__main__":
    main()
