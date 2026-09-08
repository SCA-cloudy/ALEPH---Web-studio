"""
완성 이미지 1개(1:1)를 커미션 이미지(test-assets/commission_skull_xio.jpg)로 다시 만든다.
- 배경: 본인이 커미션(의뢰)한 일러스트, 서명("xio")이 이미지 안에 그대로 남아있음.
- 문구 색: 화이트 계열(#ffffff), 서명/그림 위쪽 여백에 배치해 서명을 가리지 않도록 함.
- gen_finished_images.py와 같은 방식(Playwright로 실제 앱을 조작)으로 finished_1_1x1.png만 갱신한다.
"""
import http.server
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
FINISHED = os.path.join(ASSETS, "finished")
os.makedirs(FINISHED, exist_ok=True)
PORT = 8857


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def set_range(page, sel, value):
    page.eval_on_selector(sel, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); }", value)
    page.wait_for_timeout(80)


def set_text_color_hex(page, hexval):
    page.eval_on_selector(
        "#textColorControl .c-hex",
        "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
        hexval.replace("#", ""),
    )
    page.wait_for_timeout(80)


def main():
    httpd = start_server()
    url = f"http://127.0.0.1:{PORT}/index.html"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(200)

        page.set_input_files("#fileInput", os.path.join(ASSETS, "commission_skull_xio.jpg"))
        page.wait_for_timeout(150)
        page.fill("#textInput", "오늘도 무사히")
        page.wait_for_timeout(80)
        set_range(page, "#posX", 50)
        set_range(page, "#posY", 10)   # 위쪽 여백 — 아래쪽 서명("xio")을 가리지 않게
        set_range(page, "#fontSize", 8)
        set_text_color_hex(page, "#ffffff")
        page.eval_on_selector(
            "#strokeToggle",
            "(el, v) => { el.checked = v; el.dispatchEvent(new Event('change', {bubbles:true})); }",
            True,
        )
        page.wait_for_timeout(150)

        with page.expect_download() as dl_info:
            page.click("button:has-text('1:1 PNG 다운로드')")
        download = dl_info.value
        download.save_as(os.path.join(FINISHED, "finished_1_1x1.png"))
        print("saved finished_1_1x1.png (commission skull, white text)")

        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
