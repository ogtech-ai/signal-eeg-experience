"""Run against a local server: python tests/ui_check.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8000'); page.wait_for_function("document.querySelector('#provenance').textContent.includes('S007')")
    page.select_option('#source','synthetic'); page.wait_for_timeout(300)
    page.click('#analyze'); page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    assert page.locator('#prediction').inner_text()=='睜眼'
    page.click('#closed'); page.wait_for_timeout(200); page.click('#analyze')
    page.wait_for_function("document.querySelector('#prediction').textContent==='閉眼'")
    page.check('#artifact'); page.click('#analyze'); page.wait_for_function("document.querySelector('#status').textContent==='品質未通過'")
    assert page.locator('#prediction').inner_text()=='暫停判讀'
    with page.expect_download() as download: page.click('#download')
    assert download.value.suggested_filename=='og-eeg-review.json'
    page.uncheck('#artifact'); page.click('#play'); page.wait_for_timeout(250); assert page.locator('#cursor').inner_text()!='0.0 秒'
    page.click('#play'); page.click('#analyze'); page.wait_for_function("document.querySelector('#status').textContent==='品質通過'")
    page.wait_for_timeout(600)
    assert float(page.locator('.iris').evaluate('(e)=>getComputedStyle(e).height').replace('px',''))<30
    Path('artifacts').mkdir(exist_ok=True); page.screenshot(path='artifacts/desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844}); page.screenshot(path='artifacts/mobile.png',full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    browser.close(); print('UI passed: open/closed, artifact rejection, playback, download, mobile overflow, no JS errors')
