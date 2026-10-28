"""Record actual redesigned app operations only; no desktop or audio capture."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/recording-v2")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1080},
        record_video_dir=str(OUT),
        record_video_size={"width": 1440, "height": 1080},
        accept_downloads=True,
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000")
    page.wait_for_function("!document.querySelector('#analyze').disabled")
    assert (
        page.locator("#source").input_value() == "physionet"
    ), "Download public samples before recording the public EEG demonstration."
    page.wait_for_timeout(2500)
    page.click("#analyze")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(5000)
    page.click("#scene-play")
    page.locator("#start").press("Home")
    for _ in range(12):
        page.locator("#start").press("ArrowRight")
        page.wait_for_timeout(80)
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(2500)
    page.click("#closed")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(3500)
    page.check("#artifact")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質未通過'"
    )
    page.wait_for_timeout(3500)
    page.click("#evidence > summary")
    page.mouse.wheel(0, 480)
    page.wait_for_timeout(3500)
    with page.expect_download() as download:
        page.click("#download")
    download.value.save_as(str(OUT / "rejected-eeg-review.json"))
    page.wait_for_timeout(1500)
    page.click("#evidence > summary")
    page.mouse.wheel(0, -1000)
    page.wait_for_timeout(1000)
    page.click("#restore")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(2200)
    page.click("#open")
    page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(2000)
    page.click("#evidence > summary")
    page.mouse.wheel(0, 480)
    page.wait_for_timeout(3500)
    with page.expect_download() as download:
        page.click("#download")
    download.value.save_as(str(OUT / "public-eeg-review.json"))
    page.wait_for_timeout(1500)
    page.click("#evidence > summary")
    page.mouse.wheel(0, -1000)
    page.wait_for_timeout(1000)
    page.select_option("#source", "synthetic")
    page.wait_for_function(
        "document.querySelector('#status').textContent==='品質通過' && document.querySelector('#provenance').textContent.includes('合成訊號')"
    )
    page.wait_for_timeout(2500)
    page.click("#closed")
    page.wait_for_function(
        "document.querySelector('#prediction').textContent==='視野收合'"
    )
    page.wait_for_timeout(2500)
    page.click("#open")
    page.wait_for_function(
        "document.querySelector('#prediction').textContent==='視野展開'"
    )
    page.wait_for_timeout(2500)
    assert not errors, errors
    video = page.video
    context.close()
    video.save_as(str(OUT / "og-eeg-full-operation-v2.webm"))
    browser.close()
    print(
        json.dumps(
            {
                "video": str(OUT / "og-eeg-full-operation-v2.webm"),
                "javascript_errors": errors,
                "audio_capture": False,
            }
        )
    )
