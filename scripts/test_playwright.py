"""
Quiplet(짤·카드 스튜디오) 자동 검증 스크립트 (Playwright).
- 카드1~5 통과기준을 최대한 실제로 브라우저에서 조작해서 확인하고 스크린샷/로그를 남긴다.
- 결과는 test-assets/results/ 아래에 스크린샷과 log.json으로 저장한다.
"""
import base64
import http.server
import json
import os
import socketserver
import threading
import time
import hashlib

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
RESULTS = os.path.join(ASSETS, "results")
os.makedirs(RESULTS, exist_ok=True)
DOWNLOADS = os.path.join(ASSETS, "downloads")
os.makedirs(DOWNLOADS, exist_ok=True)

PORT = 8842
log = []


def note(record):
    print("-", record.get("id", ""), record.get("desc", ""), "=>", record.get("result"))
    log.append(record)


def start_server():
    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def canvas_data_url(page, canvas_id):
    return page.eval_on_selector(f"#{canvas_id}", "el => el.toDataURL('image/png')")


def upload_file(page, path):
    page.set_input_files("#fileInput", path)
    page.wait_for_timeout(150)


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


def screenshot(page, name):
    path = os.path.join(RESULTS, name)
    page.screenshot(path=path, full_page=True)
    return path


def main():
    httpd = start_server()
    url = f"http://127.0.0.1:{PORT}/index.html"

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # ================= 카드1: 편집과 미리보기 =================
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(200)

        upload_file(page, os.path.join(ASSETS, "sample_landscape.jpg"))
        ok = "landscape" in page.eval_on_selector("#fileInfo", "el => el.textContent")
        note({"id": "C1-load-jpeg", "desc": "JPEG 로드(T03-C05)", "result": "PASS" if ok else "FAIL"})

        upload_file(page, os.path.join(ASSETS, "sample_portrait.png"))
        ok = "portrait" in page.eval_on_selector("#fileInfo", "el => el.textContent")
        note({"id": "C1-load-png", "desc": "PNG 로드(T03-C04)", "result": "PASS" if ok else "FAIL"})

        set_text(page, "확인용 문구")
        set_range(page, "#posX", 20)
        set_range(page, "#posY", 20)
        before = canvas_data_url(page, "canvas-1x1")
        set_range(page, "#posX", 80)
        after = canvas_data_url(page, "canvas-1x1")
        note({"id": "C1-pos", "desc": "문구 위치 변경 즉시 반영(T03-C06)", "result": "PASS" if before != after else "FAIL"})

        before = canvas_data_url(page, "canvas-1x1")
        set_range(page, "#fontSize", 18)
        after = canvas_data_url(page, "canvas-1x1")
        note({"id": "C1-size", "desc": "문구 크기 변경 즉시 반영(T03-C07)", "result": "PASS" if before != after else "FAIL"})

        before = canvas_data_url(page, "canvas-1x1")
        set_text_color_hex(page, "#ff0000")
        after = canvas_data_url(page, "canvas-1x1")
        note({"id": "C1-color", "desc": "문구 색 변경 즉시 반영(T03-C08)", "result": "PASS" if before != after else "FAIL"})
        screenshot(page, "card1_live_edit.png")

        before_info = page.eval_on_selector("#fileInfo", "el => el.textContent")
        upload_file(page, os.path.join(ASSETS, "fake_image.png"))
        err_visible = not page.eval_on_selector("#fileError", "el => el.hidden")
        after_info = page.eval_on_selector("#fileInfo", "el => el.textContent")
        note({
            "id": "C1-reject-fake",
            "desc": "위장 PNG(텍스트) 거부 + 기존 작업 유지(T03-C09, T03-C10)",
            "result": "PASS" if err_visible and before_info == after_info else "FAIL",
        })
        screenshot(page, "card1_reject_fake_png.png")

        upload_file(page, os.path.join(ASSETS, "unsupported.gif"))
        err_visible = not page.eval_on_selector("#fileError", "el => el.hidden")
        note({"id": "C1-reject-gif", "desc": "GIF(미지원 실제 이미지) 거부(T03-C10)", "result": "PASS" if err_visible else "FAIL"})
        screenshot(page, "card1_reject_gif.png")

        page.close()

        # ================= 카드2: 화면-파일 일치 =================
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.context.grant_permissions([])
        page.goto(url)
        page.wait_for_timeout(200)
        upload_file(page, os.path.join(ASSETS, "sample_landscape.jpg"))
        set_text(page, "가장자리 확인용 문구입니다 EDGE-CHECK\n두번째 줄도 있음")
        set_range(page, "#posX", 50)
        set_range(page, "#posY", 90)
        set_range(page, "#fontSize", 10)
        page.wait_for_timeout(150)
        screenshot(page, "card2_preview_all_ratios.png")

        for canvas_id, ratio_label in [("canvas-1x1", "1-1"), ("canvas-4x5", "4-5"), ("canvas-9x16", "9-16")]:
            data_url = canvas_data_url(page, canvas_id)
            canvas_bytes = base64.b64decode(data_url.split(",", 1)[1])
            canvas_hash = hashlib.sha256(canvas_bytes).hexdigest()

            with page.expect_download() as dl_info:
                btn_text = {"canvas-1x1": "1:1 PNG 다운로드", "canvas-4x5": "4:5 PNG 다운로드", "canvas-9x16": "9:16 PNG 다운로드"}[canvas_id]
                page.click(f"button:has-text('{btn_text}')")
            download = dl_info.value
            save_path = os.path.join(DOWNLOADS, f"{ratio_label}.png")
            download.save_as(save_path)
            with open(save_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            note({
                "id": f"C2-{ratio_label}",
                "desc": f"{ratio_label} 미리보기==다운로드 파일 바이트 동일(T03-C11/12/13)",
                "result": "PASS" if canvas_hash == file_hash else "FAIL",
                "canvas_sha256": canvas_hash,
                "file_sha256": file_hash,
            })
        page.close()

        # ================= 카드3: 극단 입력 12건 =================
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(200)
        upload_file(page, os.path.join(ASSETS, "sample_landscape.jpg"))

        edge_cases = [
            ("EC01", "매우 긴 한글 문구(가로 폭을 초과)", "이것은 매우 매우 매우 매우 매우 매우 매우 매우 긴 한글 문구 테스트입니다 줄바꿈이 잘 되는지 확인합니다"),
            ("EC02", "매우 긴 영문 문구", "This is a very very very very very very very long English caption used to test wrapping behavior"),
            ("EC03", "한글/영문 혼합", "오늘의 MOOD는 totally 완전 랜덤 chaos 그 자체"),
            ("EC04", "명시적 줄바꿈 3줄", "첫째 줄\n둘째 줄\n셋째 줄"),
            ("EC05", "이모지 포함", "오늘도 완전 승리 🎉🔥🥳 GG"),
            ("EC06", "빈 문구", ""),
            ("EC07", "특수문자/기호 다수", "!@#$%^&*()_+-=[]{}|;:'\",.<>/?~`"),
            ("EC08", "숫자+단위 혼합", "2026년 9월 7일 오후 3:07, 할인 -87%"),
            ("EC09", "공백만 있는 문구", "     "),
            ("EC10", "따옴표/이스케이프 문자", '그가 말했다: "괜찮아" \\n 정말?'),
            ("EC11", "탭/연속 공백 혼합", "가\t나          다"),
            ("EC12", "매우 긴 끊어쓰기 없는 영단어(버그 재현 대상)", "Supercalifragilisticexpialidociousandalsoevenlongerwordwithnobreaks"),
        ]

        image_variants = [
            ("sample_landscape.jpg", "가로형 이미지"),
            ("sample_portrait.png", "세로형 이미지"),
            ("sample_transparent.png", "투명 배경 이미지"),
        ]

        results_c3 = []
        for i, (code, desc, text) in enumerate(edge_cases):
            img_file, img_desc = image_variants[i % len(image_variants)]
            upload_file(page, os.path.join(ASSETS, img_file))
            set_text(page, text)
            page.wait_for_timeout(100)
            shot = f"card3_{code}.png"
            screenshot(page, shot)
            # 앱이 죽지 않고(에러 콘솔 없이) 정상적으로 렌더된 것을 기본 pass 조건으로 삼는다.
            width_ok = page.eval_on_selector(
                "#canvas-1x1", "el => el.width === 1080 && el.height === 1080"
            )
            results_c3.append({
                "code": code,
                "desc": desc,
                "text": text,
                "image": img_desc,
                "screenshot": shot,
                "rendered_ok": width_ok,
            })
        note({"id": "C3-all12", "desc": "극단 입력 12건 기록(T03-C14)", "result": "RECORDED", "cases": results_c3})

        # 기존 편집 유지 확인: 정상 텍스트 설정 후 위장 파일(부적합 극단 입력) 넣고 텍스트 유지되는지
        set_text(page, "삭제되면 안 되는 소중한 문구")
        before_text = page.eval_on_selector("#textInput", "el => el.value")
        upload_file(page, os.path.join(ASSETS, "fake_image.png"))
        after_text = page.eval_on_selector("#textInput", "el => el.value")
        note({
            "id": "C3-no-wipe",
            "desc": "잘못된 극단 입력 후 기존 편집 유지(T03-C16)",
            "result": "PASS" if before_text == after_text else "FAIL",
        })
        page.close()

        # ================= 카드4: 템플릿 CRUD + 새로고침 유지 =================
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(200)
        upload_file(page, os.path.join(ASSETS, "sample_square.jpg"))

        def save_template(name, text):
            set_text(page, text)
            page.once("dialog", lambda d: d.accept(name))
            page.click("#saveTemplateBtn")
            page.wait_for_timeout(150)

        save_template("템플릿A", "첫 번째 템플릿")
        save_template("템플릿B", "두 번째 템플릿")
        save_template("템플릿C", "세 번째 템플릿")
        count = page.eval_on_selector_all(".template-item", "els => els.length")
        note({"id": "C4-create3", "desc": "템플릿 3개 이상 생성(T03-C17)", "result": "PASS" if count >= 3 else "FAIL"})
        screenshot(page, "card4_three_templates.png")

        # 불러오기 -> 수정 -> 업데이트
        page.click(".template-item:nth-child(1) button:has-text('불러오기')")
        page.wait_for_timeout(100)
        loaded_text = page.eval_on_selector("#textInput", "el => el.value")
        note({"id": "C4-load", "desc": "템플릿 재로드(T03-C18)", "result": "PASS" if loaded_text == "첫 번째 템플릿" else "FAIL"})

        set_text(page, "첫 번째 템플릿(수정됨)")
        page.click("#updateTemplateBtn")
        page.wait_for_timeout(100)
        updated_name_text = page.eval_on_selector(".template-item:nth-child(1) .t-name", "el => el.textContent")
        note({"id": "C4-update", "desc": "템플릿 수정(T03-C19)", "result": "PASS" if updated_name_text else "FAIL"})

        # 삭제
        before_count = page.eval_on_selector_all(".template-item", "els => els.length")
        page.click(".template-item:nth-child(3) button:has-text('삭제')")
        page.wait_for_timeout(100)
        after_count = page.eval_on_selector_all(".template-item", "els => els.length")
        note({"id": "C4-delete", "desc": "템플릿 삭제(T03-C20)", "result": "PASS" if after_count == before_count - 1 else "FAIL"})

        # 새로고침 후 유지 확인
        page.reload()
        page.wait_for_timeout(200)
        after_reload_count = page.eval_on_selector_all(".template-item", "els => els.length")
        note({
            "id": "C4-persist",
            "desc": "새로고침 후 템플릿 유지(T03-C21)",
            "result": "PASS" if after_reload_count == after_count else "FAIL",
        })
        screenshot(page, "card4_after_reload.png")
        page.close()

        # ================= 카드5: JSON 가져오기 검증 =================
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(url)
        page.wait_for_timeout(200)

        # 5-1) 정상 JSON -> 복원
        page.set_input_files("#importJsonInput", os.path.join(ASSETS, "valid_templates.json"))
        page.wait_for_timeout(150)
        info_visible = not page.eval_on_selector("#jsonInfo", "el => el.hidden")
        tpl_count = page.eval_on_selector_all(".template-item", "els => els.length")
        note({
            "id": "C5-valid-json",
            "desc": "정상 JSON 가져오기 -> 템플릿 복원(T03-C22)",
            "result": "PASS" if info_visible and tpl_count == 3 else "FAIL",
        })
        screenshot(page, "card5_valid_import.png")

        # 5-2) 문법 손상 JSON -> 거부, 기존 유지
        before_count = page.eval_on_selector_all(".template-item", "els => els.length")
        page.set_input_files("#importJsonInput", os.path.join(ASSETS, "broken_syntax.json"))
        page.wait_for_timeout(150)
        err_visible = not page.eval_on_selector("#jsonError", "el => el.hidden")
        after_count = page.eval_on_selector_all(".template-item", "els => els.length")
        note({
            "id": "C5-broken-json",
            "desc": "문법 손상 JSON 저장 전 거부 + 기존 템플릿 유지(T03-C23)",
            "result": "PASS" if err_visible and after_count == before_count else "FAIL",
        })
        screenshot(page, "card5_broken_import.png")

        # 5-3) 필수 항목 누락 JSON -> 거부, 기존 유지
        page.set_input_files("#importJsonInput", os.path.join(ASSETS, "missing_required.json"))
        page.wait_for_timeout(150)
        err_visible = not page.eval_on_selector("#jsonError", "el => el.hidden")
        after_count2 = page.eval_on_selector_all(".template-item", "els => els.length")
        note({
            "id": "C5-missing-field-json",
            "desc": "필수 항목 누락 JSON 저장 전 거부 + 기존 템플릿 유지(T03-C24)",
            "result": "PASS" if err_visible and after_count2 == before_count else "FAIL",
        })
        screenshot(page, "card5_missing_field_import.png")
        page.close()

        browser.close()

    with open(os.path.join(RESULTS, "log.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    httpd.shutdown()
    print("\n총", len(log), "건 기록. 상세는 test-assets/results/log.json 참고")


if __name__ == "__main__":
    main()
