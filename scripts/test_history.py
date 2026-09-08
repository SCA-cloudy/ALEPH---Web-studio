"""편집 기록(히스토리) 패널 동작 확인."""
import http.server
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
RESULTS = os.path.join(ASSETS, "results")
PORT = 8899


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def set_range_final(page, sel, value):
    page.eval_on_selector(
        sel,
        "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
        value,
    )
    page.wait_for_timeout(80)


def main():
    httpd = start_server()
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(f"http://127.0.0.1:{PORT}/index.html")
        page.wait_for_timeout(200)

        # 1) 이미지 로드 -> 기록 1개
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)

        # 2) 문구 변경 -> 디바운스 후 기록
        page.fill("#textInput", "첫 번째 문구")
        page.wait_for_timeout(1000)

        # 3) 위치 변경(change 이벤트) -> 기록
        set_range_final(page, "#posX", 30)

        # 4) 문구 다시 변경 -> 기록
        page.fill("#textInput", "두 번째 문구로 수정함")
        page.wait_for_timeout(1000)

        count = page.eval_on_selector_all(".history-item", "els => els.length")
        print("기록 개수(기대: 4) =", count)
        assert count == 4, f"기록 개수가 예상과 다름: {count}"

        labels = page.eval_on_selector_all(".history-item .h-label", "els => els.map(e => e.textContent)")
        print("기록 순서:", labels)

        page.screenshot(path=os.path.join(RESULTS, "history_panel_full.png"), full_page=True)

        # 5) 두 번째 기록(문구: 첫 번째 문구)을 클릭해서 되돌아가기
        page.click(".history-item:nth-child(2)")
        page.wait_for_timeout(150)
        restored_text = page.eval_on_selector("#textInput", "el => el.value")
        print("복원된 문구:", restored_text)
        assert restored_text == "첫 번째 문구", f"복원 실패: {restored_text}"

        current_label = page.eval_on_selector(".history-item.current .h-label", "el => el.textContent")
        print("현재 위치 표시:", current_label)

        page.screenshot(path=os.path.join(RESULTS, "history_panel_restored.png"), full_page=True)

        # 6) 되돌아간 상태에서 새로 편집 -> 이후 기록(3,4번)이 잘려나가고 새 기록이 붙는지 확인
        page.fill("#textInput", "분기된 새 문구")
        page.wait_for_timeout(1000)
        count_after_branch = page.eval_on_selector_all(".history-item", "els => els.length")
        labels_after_branch = page.eval_on_selector_all(".history-item .h-label", "els => els.map(e => e.textContent)")
        print("분기 후 기록 개수(기대: 3) =", count_after_branch)
        print("분기 후 기록 순서:", labels_after_branch)
        assert count_after_branch == 3, f"분기 처리 실패: {count_after_branch}"

        page.screenshot(path=os.path.join(RESULTS, "history_panel_branched.png"), full_page=True)

        b.close()
    httpd.shutdown()
    print("\n편집 기록 패널 동작 확인 완료: 전부 통과")


if __name__ == "__main__":
    main()
