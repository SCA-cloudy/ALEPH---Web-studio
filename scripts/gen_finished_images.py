"""
제출용 '완성 이미지' 3개를 실제 앱으로 만들어 test-assets/finished/ 에 저장한다.
서로 다른 문구/비율을 사용한다. 배경 이미지는 모두 scripts/gen_assets.py 가 코드로
직접 그린 자작 이미지이므로 전부 본인 제작으로 기록한다.
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
PORT = 8853


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def set_text(page, text):
    page.fill("#textInput", text)
    page.wait_for_timeout(80)


def set_range(page, sel, value):
    page.eval_on_selector(sel, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); }", value)
    page.wait_for_timeout(80)


def set_color(page, sel, hexval):
    page.eval_on_selector(sel, "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); }", hexval)
    page.wait_for_timeout(80)


def set_text_color_hex(page, hexval):
    """#textColor는 재사용 색상 컨트롤(HEX/RGB + 그라데이션)로 바뀌어서, 그 안의 HEX 입력칸에 값을 넣는다."""
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

        jobs = [
            {
                "image": "sample_landscape.jpg",
                "text": "가을 신메뉴 출시 🍁",
                "x": 50, "y": 88, "fontSize": 9, "color": "#ffffff", "stroke": True,
                "canvas": "canvas-1x1", "out": "finished_1_1x1.png",
            },
            {
                "image": "sample_portrait.png",
                "text": "오늘의 한마디\n\"작게 시작해도 괜찮다\"",
                "x": 50, "y": 15, "fontSize": 7, "color": "#12233a", "stroke": False,
                "canvas": "canvas-4x5", "out": "finished_2_4x5.png",
            },
            {
                "image": "sample_transparent.png",
                "text": "월요일의 나 vs 금요일의 나",
                "x": 50, "y": 78, "fontSize": 5, "color": "#ffe082", "stroke": True,
                "canvas": "canvas-9x16", "out": "finished_3_9x16.png",
            },
        ]

        for job in jobs:
            page.set_input_files("#fileInput", os.path.join(ASSETS, job["image"]))
            page.wait_for_timeout(150)
            set_text(page, job["text"])
            set_range(page, "#posX", job["x"])
            set_range(page, "#posY", job["y"])
            set_range(page, "#fontSize", job["fontSize"])
            set_text_color_hex(page, job["color"])
            page.eval_on_selector(
                "#strokeToggle",
                "(el, v) => { el.checked = v; el.dispatchEvent(new Event('change', {bubbles:true})); }",
                job["stroke"],
            )
            page.wait_for_timeout(150)
            btn_map = {"canvas-1x1": "1:1 PNG 다운로드", "canvas-4x5": "4:5 PNG 다운로드", "canvas-9x16": "9:16 PNG 다운로드"}
            with page.expect_download() as dl_info:
                page.click(f"button:has-text('{btn_map[job['canvas']]}')")
            download = dl_info.value
            download.save_as(os.path.join(FINISHED, job["out"]))
            print("saved", job["out"])

        browser.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
