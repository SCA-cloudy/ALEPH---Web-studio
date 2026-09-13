"""과제5 카드1 고정 검사 TC01~TC10: Ctrl+Z/Ctrl+Shift+Z 키보드 단축키 동작 확인."""
import http.server
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
PORT = 8900

results = []  # (id, passed, detail)


def record(tc_id, passed, detail):
    results.append((tc_id, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {tc_id}: {detail}")


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


def blur_text_input(page):
    """문구 입력창 포커스를 캔버스 쪽으로 옮겨(커밋 완료 상태로) 이후 키보드 단축키가
    앱 히스토리(restoreHistory)를 향하게 만든다. TC08(포커스 유지 케이스)에서는 호출하지 않는다."""
    page.eval_on_selector("#textInput", "el => el.blur()")
    page.wait_for_timeout(50)


def press_undo(page):
    page.keyboard.press("Control+z")
    page.wait_for_timeout(120)


def press_redo(page):
    page.keyboard.press("Control+Shift+Z")
    page.wait_for_timeout(120)


def current_label(page):
    items = page.eval_on_selector_all(".history-item.current .h-label", "els => els.map(e => e.textContent)")
    return items[0] if items else None


def item_count(page):
    return page.eval_on_selector_all(".history-item", "els => els.length")


def goto_fresh(page, base_url):
    page.goto(base_url)
    page.wait_for_timeout(200)


def main():
    httpd = start_server()
    console_errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        base_url = f"http://127.0.0.1:{PORT}/index.html"

        # ---------------- TC03: 기록 0개 상태에서 Ctrl+Z ----------------
        goto_fresh(page, base_url)
        press_undo(page)
        empty_hidden = page.eval_on_selector("#historyEmpty", "el => el.hidden")
        record("TC03", empty_hidden is False, f"historyEmpty.hidden={empty_hidden}(기대 False=계속 보임), 콘솔오류={len(console_errors)}건")

        # ---------------- TC01: 기본 undo 1회 ----------------
        goto_fresh(page, base_url)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        set_range_final(page, "#posX", 30)
        press_undo(page)
        posx_val = page.eval_on_selector("#posX", "el => el.value")
        lbl = current_label(page)
        record("TC01", posx_val == "50" and lbl and lbl.startswith("이미지 불러옴"),
               f"posX={posx_val}(기대 50), current label='{lbl}'")

        # ---------------- TC02: 문구 undo ----------------
        goto_fresh(page, base_url)
        page.fill("#textInput", "첫 번째 문구")
        page.wait_for_timeout(1000)
        page.fill("#textInput", "두 번째 문구로 수정함")
        page.wait_for_timeout(1000)
        blur_text_input(page)
        press_undo(page)
        text_val = page.eval_on_selector("#textInput", "el => el.value")
        record("TC02", text_val == "첫 번째 문구", f"#textInput 값='{text_val}'(기대 '첫 번째 문구')")

        # ---------------- TC04: 하한(가장 오래된 기록) 경계 ----------------
        goto_fresh(page, base_url)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        set_range_final(page, "#posX", 30)
        page.fill("#textInput", "문구A")
        page.wait_for_timeout(1000)
        blur_text_input(page)
        press_undo(page)
        lbl1 = current_label(page)
        press_undo(page)
        lbl2 = current_label(page)
        press_undo(page)  # 3번째: 더 내려갈 곳 없음
        lbl3 = current_label(page)
        record("TC04", lbl2 and lbl2.startswith("이미지 불러옴") and lbl3 == lbl2,
               f"2회 undo 후='{lbl2}', 3회 undo 후='{lbl3}'(동일해야 함, 즉 무반응)")

        # ---------------- TC05: undo 2회 -> redo 1회 ----------------
        goto_fresh(page, base_url)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        set_range_final(page, "#posX", 30)
        page.fill("#textInput", "문구A")
        page.wait_for_timeout(1000)
        blur_text_input(page)
        press_undo(page)
        press_undo(page)
        press_redo(page)
        lbl = current_label(page)
        record("TC05", lbl is not None and lbl.startswith("가로 위치 변경"), f"redo 후 current label='{lbl}'(기대: '가로 위치 변경: 30%')")

        # ---------------- TC06: 상한(가장 최신 기록) 경계 ----------------
        goto_fresh(page, base_url)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        set_range_final(page, "#posX", 30)
        tip_label = current_label(page)
        press_redo(page)
        press_redo(page)
        press_redo(page)
        lbl = current_label(page)
        cnt = item_count(page)
        record("TC06", lbl == tip_label and cnt == 2, f"redo 3회 후 label='{lbl}'(변화없어야 함, 기대 '{tip_label}'), 기록수={cnt}(기대 2)")

        # ---------------- TC07: undo 후 새 편집 -> 분기(미래 기록 삭제) ----------------
        goto_fresh(page, base_url)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        set_range_final(page, "#posX", 30)
        page.fill("#textInput", "문구A")
        page.wait_for_timeout(1000)
        blur_text_input(page)
        press_undo(page)
        press_undo(page)  # index 0, redo 가능한 상태(future 2개 존재)
        set_range_final(page, "#posY", 77)  # 새 편집 -> branch
        cnt_after_branch = item_count(page)
        press_redo(page)  # 더 이상 미래 없음 -> 무반응
        lbl = current_label(page)
        record("TC07", cnt_after_branch == 2 and lbl and lbl.startswith("세로 위치 변경"),
               f"분기 후 기록수={cnt_after_branch}(기대 2), redo 후 label='{lbl}'(기대: '세로 위치 변경: 77%' 유지)")

        # ---------------- TC08: 텍스트박스 포커스 중 Ctrl+Z 무시 ----------------
        goto_fresh(page, base_url)
        page.fill("#textInput", "임시 문구")
        page.wait_for_timeout(1000)
        before_lbl = current_label(page)
        before_cnt = item_count(page)
        page.focus("#textInput")
        press_undo(page)
        after_lbl = current_label(page)
        after_cnt = item_count(page)
        record("TC08", before_lbl == after_lbl and before_cnt == after_cnt,
               f"포커스 상태 Ctrl+Z 전후 label='{before_lbl}'->'{after_lbl}', 기록수={before_cnt}->{after_cnt}(변화 없어야 함)")

        # ---------------- TC09: 마우스 클릭 이동 + 키보드 공유 포인터 ----------------
        goto_fresh(page, base_url)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        set_range_final(page, "#posX", 30)
        page.fill("#textInput", "문구A")
        page.wait_for_timeout(1000)
        page.click(".history-item:nth-child(2)")  # index1(가로 위치 변경)으로 마우스 이동
        page.wait_for_timeout(100)
        mid_lbl = current_label(page)
        press_undo(page)
        after_lbl = current_label(page)
        record("TC09", mid_lbl and mid_lbl.startswith("가로 위치") and after_lbl and after_lbl.startswith("이미지 불러옴"),
               f"클릭 이동 후='{mid_lbl}', 이어서 Ctrl+Z 후='{after_lbl}'(기대: 이미지 불러옴 항목)")

        # ---------------- TC10: 대량 연속 입력 내구성 ----------------
        goto_fresh(page, base_url)
        for v in range(10, 101, 10):
            set_range_final(page, "#posX", v)
        cnt_before = item_count(page)
        exc = None
        try:
            for _ in range(20):
                page.keyboard.press("Control+z")
            page.wait_for_timeout(300)
        except Exception as e:  # noqa
            exc = str(e)
        final_lbl = current_label(page)
        cnt_after = item_count(page)
        record("TC10", exc is None and cnt_before == cnt_after == 10 and final_lbl and "10%" in final_lbl,
               f"예외={exc}, 기록수 {cnt_before}->{cnt_after}(변화없어야), 최종 label='{final_lbl}'(기대: 가로 위치 변경: 10%)")

        b.close()
    httpd.shutdown()

    print("\n=== 콘솔/페이지 오류 목록 ===")
    for e in console_errors:
        print(" -", e)
    print(f"\n=== 결과 요약: {sum(1 for _, p, _ in results if p)}/{len(results)} PASS ===")
    for tc_id, passed, detail in results:
        print(f"{tc_id}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()
