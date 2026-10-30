"""End-to-end report workflow: CSV, privacy, evidence navigation and print CSS."""

import hashlib
import json
import csv
import io
from pathlib import Path
import numpy as np
from playwright.sync_api import sync_playwright

OUT = Path("artifacts/report-qa")
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000}, device_scale_factor=1
    )
    page = context.new_page()
    errors = []
    requests = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "request", lambda r: requests.append({"url": r.url, "body": r.post_data or ""})
    )
    page.goto("http://127.0.0.1:8000")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='報告已產生'"
    )
    assert page.locator("#report-case").inner_text() == "DEMO-001"
    assert "完全虛構" in page.locator("#profile-context").inner_text()
    assert page.locator("#bands .band-item").count() == 4
    assert page.locator("#window-table tr").count() > 0
    page.screenshot(path=str(OUT / "desktop-preview.png"), full_page=True)
    before = len(requests)
    page.locator("#window-table tr").last.click()
    assert page.locator("#window-select").input_value() == str(
        page.locator("#window-table tr").count() - 1
    )
    assert len(requests) == before
    page.select_option("#source", "synthetic-artifacts")
    assert page.locator("#print-report").is_disabled()
    page.click("#generate")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='報告已產生'"
    )
    assert (
        "A1" in page.locator("#window-table").inner_text()
        and "A2" in page.locator("#window-table").inner_text()
    )
    page.locator(".evidence-link").first.click()
    assert "PTP" in page.locator("#selected-evidence").inner_text()
    page.screenshot(path=str(OUT / "synthetic-artifact-report.png"), full_page=True)
    page.select_option("#case-preset", "custom")
    page.fill("#case-code", "QA-ANON-PRIVATE-DO-NOT-SEND")
    page.fill("#age", "35")
    page.fill("#sleep", "5")
    page.fill("#caffeine", "3")
    page.check("#shift")
    page.select_option("#source", "upload")
    t = np.arange(160 * 12) / 160
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["time_s", "O1_uV"])
    for i, value in enumerate(20 * np.sin(2 * np.pi * 10 * t)):
        writer.writerow([format(i / 160, ".17g"), format(value, ".17g")])
    raw = output.getvalue().encode()
    page.locator("#eeg-file").set_input_files(
        {
            "name": "QA-ANON-PRIVATE-DO-NOT-SEND.csv",
            "mimeType": "text/csv",
            "buffer": raw,
        }
    )
    page.select_option("#condition", "eyes_closed")
    page.click("#generate")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='報告已產生'"
    )
    assert page.locator("#report-case").inner_text() == "QA-ANON-PRIVATE-DO-NOT-SEND"
    assert "閉眼" in page.locator("#report-condition").inner_text()
    assert all(
        "QA-ANON-PRIVATE-DO-NOT-SEND" not in r["url"] + r["body"] for r in requests
    )
    assert page.evaluate("localStorage.length===0 && sessionStorage.length===0")
    with page.expect_download() as d:
        page.click("#export-json")
    path = OUT / "uploaded-evidence.json"
    d.value.save_as(str(path))
    data = json.loads(path.read_text())
    assert data["case_background"]["code"] == "QA-ANON-PRIVATE-DO-NOT-SEND"
    assert data["analysis"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    with page.expect_download() as d:
        page.click("#download-raw")
    original = OUT / "roundtrip.csv"
    d.value.save_as(str(original))
    assert original.read_bytes() == raw
    page.locator("#eeg-file").set_input_files(
        {
            "name": "invalid.csv",
            "mimeType": "text/csv",
            "buffer": b"time_s,O1_uV\n0,nan\n",
        }
    )
    page.click("#generate")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='請檢查輸入'"
    )
    assert (
        "NaN" in page.locator("#error").inner_text()
        and page.locator("#print-report").is_disabled()
    )
    page.locator("#eeg-file").set_input_files(
        {"name": "unsupported.edf", "mimeType": "application/edf", "buffer": b"not edf"}
    )
    assert (
        "只支援" in page.locator("#error").inner_text()
        and page.locator("#generate").is_disabled()
    )
    # Demo remains available even after bad uploaded data. Clear actually removes the work session.
    page.select_option("#source", "synthetic-clean")
    page.click("#generate")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='報告已產生'"
    )
    page.click("#clear-session")
    assert page.locator("#report").is_hidden()
    assert (
        page.locator("#case-code").input_value() == "DEMO-001"
        and page.locator("#eeg-file").input_value() == ""
    )
    page.click("#generate")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='報告已產生'"
    )
    # CI must not depend on optional downloaded recordings. Exercise the real
    # synthetic report path on every viewport rather than treating option
    # actionability as evidence that its dataset exists.
    catalog = page.request.get("http://127.0.0.1:8000/api/report/catalog").json()
    if not catalog["public_available"]:
        for source in ("public-open", "public-closed"):
            option = page.locator(f'#source option[value="{source}"]')
            assert option.get_attribute("disabled") is not None
            missing = page.request.get(
                f"http://127.0.0.1:8000/api/report/demo?source={source}"
            )
            assert missing.status == 409
            assert "公開樣本尚未下載" in missing.json()["detail"]
    page.select_option("#source", "synthetic-clean")
    page.click("#generate")
    page.wait_for_function(
        "document.querySelector('#phase').textContent==='報告已產生'"
    )
    analysis = page.request.get(
        "http://127.0.0.1:8000/api/report/demo?source=synthetic-clean"
    ).json()
    assert analysis["source"]["kind"] == "synthetic"
    assert analysis["quality"]["included_windows"] == 10
    (OUT / "synthetic-analysis.json").write_text(json.dumps(analysis, indent=2))
    page.locator("h1").click()
    page.screenshot(path=str(OUT / "desktop-preview.png"), full_page=True)
    for width, height in ((1280, 900), (390, 844), (360, 800)):
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(250)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
        if width < 800:
            assert not page.locator("#workflow-details").evaluate("e=>e.open")
            page.locator("#workflow-details > summary").click()
            page.select_option("#source", "synthetic-artifacts")
            page.click("#generate")
            page.wait_for_function(
                "document.querySelector('#phase').textContent==='報告已產生'"
            )
            assert not page.locator("#workflow-details").evaluate("e=>e.open")
            page.locator("#window-table tr").nth(2).click()
            assert page.locator("#window-select").input_value() == "2"
            page.locator("#workflow-details > summary").click()
            page.select_option("#source", "synthetic-clean")
            page.click("#generate")
            page.wait_for_function(
                "document.querySelector('#phase').textContent==='報告已產生'"
            )
        page.locator("h1").click()
        page.screenshot(path=str(OUT / f"preview-{width}.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    # The actual application exposes browser Print / Save as PDF. PDF is generated through identical print CSS.
    page.evaluate(
        "window.__printRequested=false; window.print=()=>{window.__printRequested=true}"
    )
    page.click("#print-report")
    assert page.evaluate("window.__printRequested")
    page.emulate_media(media="print")
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    Path("output/pdf").mkdir(parents=True, exist_ok=True)
    page.pdf(
        path="output/pdf/OG_EEG_Synthetic_Sample_Report.pdf",
        format="A4",
        print_background=True,
        prefer_css_page_size=True,
    )
    assert not errors, errors
    context.close()
    browser.close()
    print(
        "Report UI passed: fictional case, real CSV upload, no profile transmission/storage, original download, masks/navigation, validation/recovery, mobile workflow, real print PDF, no JS errors"
    )
