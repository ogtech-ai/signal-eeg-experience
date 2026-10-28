"""Record real report-workbench operations; application viewport only, no audio."""

from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/report-recording")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        record_video_dir=str(OUT),
        record_video_size={"width": 1440, "height": 1000},
        accept_downloads=True,
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8000")

    def ready():
        page.wait_for_function(
            "document.querySelector('#phase').textContent==='報告已產生'"
        )
        page.wait_for_timeout(1800)

    ready()
    assert page.locator("#source").input_value() == "public-open"
    page.wait_for_timeout(1800)
    page.select_option("#source", "public-closed")
    page.click("#generate")
    ready()
    page.locator("#window-table tr").nth(1).click()
    page.locator("#selected-evidence").scroll_into_view_if_needed()
    page.wait_for_timeout(2500)
    page.locator(".observations-section").scroll_into_view_if_needed()
    page.wait_for_timeout(3000)
    page.locator(".methods-section").scroll_into_view_if_needed()
    page.wait_for_timeout(3000)
    page.locator("h1").click()
    page.select_option("#source", "synthetic-artifacts")
    page.click("#generate")
    ready()
    page.locator(".evidence-link").first.click()
    page.wait_for_timeout(2500)
    page.locator("#window-table").scroll_into_view_if_needed()
    page.wait_for_timeout(3000)
    page.locator("h1").click()
    # Real upload uses a downloaded, legally public demo CSV, never a patient recording.
    response = page.request.get(
        "http://127.0.0.1:8000/api/report/demo.csv?source=public-open"
    )
    assert response.ok
    page.select_option("#source", "upload")
    page.locator("#eeg-file").set_input_files(
        {
            "name": "PhysioNet-S008-R01-public.csv",
            "mimeType": "text/csv",
            "buffer": response.body(),
        }
    )
    page.wait_for_timeout(1500)
    page.click("#generate")
    ready()
    with page.expect_download() as download:
        page.click("#export-json")
    download.value.save_as(str(OUT / "public-upload-report.json"))
    page.wait_for_timeout(1600)
    page.locator(".spectral-grid").scroll_into_view_if_needed()
    page.wait_for_timeout(3000)
    page.locator(".methods-section").scroll_into_view_if_needed()
    page.wait_for_timeout(3000)
    page.locator("h1").click()
    # Return to explicitly labeled public source for final print artifact.
    page.select_option("#source", "public-open")
    page.click("#generate")
    ready()
    page.screenshot(path=str(OUT / "desktop-report.png"))
    page.click("#print-report")
    page.wait_for_timeout(1500)
    page.emulate_media(media="print")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    page.pdf(
        path=str(OUT / "public-report.pdf"),
        print_background=True,
        prefer_css_page_size=True,
    )
    page.emulate_media(media="screen")
    page.wait_for_timeout(1800)
    assert not errors, errors
    video = page.video
    context.close()
    video.save_as(str(OUT / "OG_EEG_Report_Workflow_Silent.webm"))
    browser.close()
    print(
        "Recorded actual public/synthetic/upload/report/evidence/export/print workflow; no audio capture."
    )
