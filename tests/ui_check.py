"""Local browser acceptance: real data flow, visual states, responsiveness and races."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/ui-redesign")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000}, device_scale_factor=1
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8000")
    page.wait_for_function("!document.querySelector('#analyze').disabled")
    page.screenshot(path=str(OUT / "desktop-first-use.png"), full_page=True)
    assert page.locator("#probability").inner_text().startswith("—")
    assert page.locator("#analyze-label").inner_text() == "開始體驗"
    cursor_before = page.locator("#cursor").inner_text()
    page.click("#analyze")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(350)
    assert page.locator("#cursor").inner_text() != cursor_before
    page.click("#play")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / "desktop-public-open.png"), full_page=True)
    initial_opening = page.locator("#scene").evaluate(
        "e=>e.style.getPropertyValue('--opening')"
    )
    page.click("#closed")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(1200)
    assert (
        page.locator("#scene").evaluate("e=>e.style.getPropertyValue('--opening')")
        != initial_opening
    )
    page.screenshot(path=str(OUT / "desktop-public-closed.png"), full_page=True)
    page.check("#artifact")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質未通過'"
    )
    assert page.locator("#probability").inner_text().startswith("—")
    assert (
        page.locator("#probability-fill").evaluate("e=>e.getBoundingClientRect().width")
        == 0
    )
    assert page.locator("#prediction").inner_text() == "暫停判讀"
    assert page.locator("#restore").is_visible()
    page.screenshot(path=str(OUT / "desktop-rejected.png"), full_page=True)
    page.click("#evidence > summary")
    with page.expect_download() as download:
        page.click("#download")
    assert download.value.suggested_filename == "og-eeg-review.json"
    saved = OUT / "qa-rejected-review.json"
    download.value.save_as(str(saved))
    report = json.loads(saved.read_text())
    assert report["closed_probability"] is None and report["artifact_injected"]
    page.screenshot(path=str(OUT / "desktop-evidence.png"), full_page=True)
    page.click("#evidence > summary")
    page.click("#restore")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.select_option("#source", "synthetic")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質通過' && document.querySelector('#provenance').textContent.includes('合成訊號')"
    )
    assert page.locator("#prediction").inner_text() == "視野收合"
    page.click("#open")
    page.wait_for_function(
        "document.querySelector('#prediction').textContent==='視野展開'"
    )
    # Rapid input changes invalidate older responses. Only the final chosen sample may win.
    page.click("#closed")
    page.click("#open")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質通過' && document.querySelector('#prediction').textContent==='視野展開'"
    )
    page.locator("#start").press("Home")
    page.locator("#start").press("ArrowRight")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    assert page.locator("#time").inner_text().startswith("00:01")
    for width, height in ((1280, 900), (390, 844), (360, 800)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(300)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
        page.locator("h1").click()
        page.screenshot(path=str(OUT / f"viewport-{width}.png"), full_page=True)
    # A real request still controls the responsive UI, not a screenshot or decorative animation.
    page.click("#closed")
    page.wait_for_function(
        "document.querySelector('#prediction').textContent==='視野收合'"
    )
    page.check("#artifact")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質未通過'"
    )
    page.screenshot(path=str(OUT / "mobile-rejected.png"), full_page=True)
    page.click("#restore")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    # Hold a real server response, complete a newer request, then release the stale one.
    page.set_viewport_size({"width": 1440, "height": 1000})
    held = []

    def delay_first_analysis(route):
        if not held:
            held.append([route, None])
            held[0][1] = route.fetch()
        else:
            route.continue_()

    page.route("**/api/analyze", delay_first_analysis)
    page.click("#open")
    page.wait_for_function("document.querySelector('#status').textContent==='分析中…'")
    for _ in range(40):
        if held and held[0][1] is not None:
            break
        page.wait_for_timeout(50)
    assert held and held[0][1] is not None
    page.click("#closed")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質通過' && document.querySelector('#prediction').textContent==='視野收合'"
    )
    held[0][0].fulfill(response=held[0][1])
    page.wait_for_timeout(250)
    assert page.locator("#prediction").inner_text() == "視野收合"
    assert page.locator("#open").get_attribute("aria-pressed") == "false"
    page.unroute("**/api/analyze", delay_first_analysis)
    page.emulate_media(reduced_motion="reduce")
    page.screenshot(path=str(OUT / "desktop-reduced-motion.png"), full_page=True)
    # A fresh narrow first-use view must retain the main action and real signal.
    fresh = context.new_page()
    fresh.set_viewport_size({"width": 390, "height": 844})
    fresh.on("pageerror", lambda error: errors.append(str(error)))
    fresh.goto("http://127.0.0.1:8000")
    fresh.wait_for_function("!document.querySelector('#analyze').disabled")
    assert fresh.locator("#analyze").is_visible()
    assert fresh.locator("#probability").inner_text().startswith("—")
    fresh.screenshot(path=str(OUT / "mobile-first-use.png"), full_page=True)
    fresh.close()

    # Errors clear the prior prediction instead of silently substituting synthetic data.
    def unavailable_record(route):
        route.fulfill(
            status=409,
            content_type="application/json",
            body='{"detail":"測試：錄製樣本暫時不可用"}',
        )

    page.route("**/api/record?*", unavailable_record)
    page.click("#open")
    page.wait_for_function("document.querySelector('#status').textContent==='分析失敗'")
    assert page.locator("#analyze").is_disabled()
    assert page.locator("#probability").inner_text().startswith("—")
    assert "暫時不可用" in page.locator("#error").inner_text()
    page.unroute("**/api/record?*", unavailable_record)
    page.click("#closed")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    assert not errors, errors
    context.close()
    browser.close()
    print(
        "UI passed: first use, real/synthetic auto inference, scene response, quality refusal/recovery, JSON provenance, rapid-switch races, timeline, 1280/390/360 layouts, no JS errors"
    )
