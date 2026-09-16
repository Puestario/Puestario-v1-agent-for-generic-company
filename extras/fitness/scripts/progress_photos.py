#!/usr/bin/env python3
"""
Download a client's progress photos from the coaching platform at
YOUR_PLATFORM_URL.
Saves: before_front.jpg, before_side.jpg, before_back.jpg,
       after_front.jpg, after_side.jpg, after_back.jpg

Requires: playwright (pip install playwright && playwright install chromium)

YOUR_PLATFORM_URL and the login credentials are read from the environment at
run time, as PLATFORM_URL, PLATFORM_EMAIL and PLATFORM_PASSWORD. There is
nothing to edit below — replacing the placeholder in this docstring configures
nothing. Export the three variables before running or the script exits 1.

PLATFORM-SPECIFIC. The login selectors (#emailInput, #passInput), the URL
paths (/app/login and /app/client/<id>/progress/photo), the "Load More"
button text, and the Front/Side/Back photo labels below are all shaped to
one particular platform's page structure. Pointed at a different platform
this does not error — it logs in, matches nothing, and reports zero photos
found. Re-derive every selector against your own platform before trusting
the output.
"""
import asyncio
import sys
import os
import base64
import json
from pathlib import Path


async def get_photos(client_id: str, output_dir: str = "/tmp/client_photos"):
    from playwright.async_api import async_playwright

    # Load credentials from environment — set these before running
    platform_url = os.environ.get("PLATFORM_URL")
    login_email  = os.environ.get("PLATFORM_EMAIL")
    login_password = os.environ.get("PLATFORM_PASSWORD")

    if not all([platform_url, login_email, login_password]):
        print("ERROR: Set PLATFORM_URL, PLATFORM_EMAIL, and PLATFORM_PASSWORD env vars")
        sys.exit(1)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        print("Logging in...")
        await page.goto(f"{platform_url}/app/login", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await page.fill('#emailInput', login_email)
        await page.fill('#passInput', login_password)
        await page.press('#passInput', "Enter")
        await asyncio.sleep(5)

        await page.goto(f"{platform_url}/app/client/{client_id}/progress/photo", wait_until="domcontentloaded")
        await asyncio.sleep(6)

        # Load all photos
        load_more_clicks = 0
        while True:
            try:
                btn = await page.wait_for_selector('button:has-text("Load More")', timeout=3000)
                if btn:
                    await btn.click()
                    await asyncio.sleep(3)
                    load_more_clicks += 1
                else:
                    break
            except:
                break

        # Extract photos with labels and dates
        all_photos = await page.evaluate("""
            () => {
                const results = [];
                const allEls = document.querySelectorAll('*');
                allEls.forEach(el => {
                    const bg = window.getComputedStyle(el).backgroundImage;
                    if (bg && bg !== 'none' && bg.startsWith('url("data:image')) {
                        const dataUrl = bg.slice(5, -2);
                        let label = '';
                        let date = '';
                        let searchEl = el;
                        for (let i = 0; i < 5; i++) {
                            searchEl = searchEl?.parentElement;
                            if (!searchEl) break;
                            const ps = searchEl.querySelectorAll('p');
                            ps.forEach(p => {
                                const t = p.textContent?.trim();
                                if (['Front', 'Side', 'Back'].includes(t)) label = t;
                                if (t && t.match(/^\\d{4}-\\d{2}-\\d{2}$/)) date = t;
                            });
                            if (label && date) break;
                        }
                        results.push({ label, date, dataUrl });
                    }
                });
                return results;
            }
        """)

        print(f"Total photos found: {len(all_photos)}")

        by_date = {}
        for photo in all_photos:
            d = photo['date']
            l = photo['label']
            if d and l:
                if d not in by_date:
                    by_date[d] = {}
                by_date[d][l] = photo['dataUrl']

        dates = sorted(by_date.keys())
        print(f"Dates found: {dates}")

        if not dates:
            print("No labeled photos found.")
            await browser.close()
            return

        first_date = dates[0]
        last_date = dates[-1]
        print(f"BEFORE date: {first_date}")
        print(f"AFTER date: {last_date}")

        saved = []
        for view in ['Front', 'Side', 'Back']:
            for timing, date_key in [("before", first_date), ("after", last_date)]:
                if view in by_date.get(date_key, {}):
                    data_url = by_date[date_key][view]
                    if ',' in data_url:
                        b64 = data_url.split(',', 1)[1]
                        img_bytes = base64.b64decode(b64)
                        fname = out / f"{timing}_{view.lower()}.jpg"
                        with open(fname, 'wb') as f:
                            f.write(img_bytes)
                        saved.append(str(fname))
                        print(f"Saved {timing} {view}: {fname}")

        await browser.close()
        print(f"\nSaved {len(saved)} photos")
        return saved, first_date, last_date


if __name__ == "__main__":
    client_id = sys.argv[1] if len(sys.argv) > 1 else "YOUR_DEFAULT_CLIENT_ID"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/client_photos"
    result = asyncio.run(get_photos(client_id, output_dir))
