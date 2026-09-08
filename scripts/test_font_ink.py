"""글꼴 선택 + 손글씨(필기, Pointer Events/압력) 기능 검증."""
import base64
import hashlib
import http.server
import json
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
RESULTS = os.path.join(ASSETS, "results")
PORT = 8901


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def canvas_hash(page, canvas_id):
    data_url = page.eval_on_selector(f"#{canvas_id}", "el => el.toDataURL('image/png')")
    return hashlib.sha256(base64.b64decode(data_url.split(",", 1)[1])).hexdigest()


def dispatch_pen_stroke(page, canvas_id, points, pointer_id=101):
    """points: [(xRatio, yRatio, pressure), ...] — xRatio/yRatio는 캔버스 표시 영역(0~1) 기준."""
    page.eval_on_selector(
        f"#{canvas_id}",
        """
        (canvas, args) => {
          const rect = canvas.getBoundingClientRect();
          const mk = (type, xr, yr, pressure) => new PointerEvent(type, {
            bubbles: true, cancelable: true,
            clientX: rect.left + rect.width * xr,
            clientY: rect.top + rect.height * yr,
            pointerId: args.pointerId, pointerType: 'pen', pressure,
          });
          const pts = args.points;
          canvas.dispatchEvent(mk('pointerdown', pts[0][0], pts[0][1], pts[0][2]));
          for (let i = 1; i < pts.length; i++) {
            canvas.dispatchEvent(mk('pointermove', pts[i][0], pts[i][1], pts[i][2]));
          }
          canvas.dispatchEvent(mk('pointerup', pts[pts.length - 1][0], pts[pts.length - 1][1], pts[pts.length - 1][2]));
        }
        """,
        {"points": points, "pointerId": pointer_id},
    )


def main():
    httpd = start_server()
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(f"http://127.0.0.1:{PORT}/index.html")
        page.wait_for_timeout(300)  # 구글 폰트 로드 대기
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        page.fill("#textInput", "글꼴 테스트")
        page.wait_for_timeout(150)

        # ---- 1) 글꼴 변경이 실제로 캔버스 픽셀을 바꾸는지 ----
        before = canvas_hash(page, "canvas-1x1")
        page.select_option("#fontFamily", "blackhan")
        page.wait_for_timeout(400)  # 웹폰트 적용 대기
        after = canvas_hash(page, "canvas-1x1")
        results.append({"id": "FONT-change", "desc": "글꼴 변경 시 캔버스 픽셀 변화", "result": "PASS" if before != after else "FAIL"})

        page.select_option("#fontFamily", "pen")
        page.wait_for_timeout(400)
        after_pen = canvas_hash(page, "canvas-1x1")
        results.append({"id": "FONT-pen", "desc": "손글씨체(Nanum Pen Script) 적용 시 픽셀 변화", "result": "PASS" if after_pen != after else "FAIL"})
        page.screenshot(path=os.path.join(RESULTS, "font_pen_style.png"), full_page=True)

        page.select_option("#fontFamily", "default")
        page.wait_for_timeout(200)

        # ---- 2) 문구 레이어가 선택된 상태(손글씨 레이어 아님)에서는 그려지지 않아야 함 ----
        before_off = canvas_hash(page, "canvas-1x1")
        dispatch_pen_stroke(page, "canvas-1x1", [(0.2, 0.2, 0.5), (0.3, 0.3, 0.5), (0.4, 0.2, 0.5)])
        page.wait_for_timeout(150)
        after_off = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "INK-off-noop",
            "desc": "손글씨 레이어를 선택하지 않은 상태에서는 캔버스에 그려지지 않음",
            "result": "PASS" if before_off == after_off else "FAIL",
        })

        # ---- 3) "+ 손글씨"로 손글씨 레이어를 추가하고 선택 -> 펜(압력 포함)으로 그리면 반영 ----
        page.click("#addInkLayerBtn")
        page.wait_for_timeout(100)
        before_on = canvas_hash(page, "canvas-1x1")
        # 압력이 점점 강해지는(0.2 -> 1.0) 곡선 하나
        stroke_points = [(0.15 + i * 0.03, 0.4 + (0.05 if i % 2 else -0.05), 0.2 + i * 0.08) for i in range(10)]
        dispatch_pen_stroke(page, "canvas-1x1", stroke_points, pointer_id=201)
        page.wait_for_timeout(200)
        after_on = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "INK-draw",
            "desc": "필기 모드 켜짐 + 펜 압력 스트로크 -> 캔버스에 반영",
            "result": "PASS" if before_on != after_on else "FAIL",
        })
        history_count_after_stroke = page.eval_on_selector_all(".history-item", "els => els.length")

        # ---- 4) 미리보기==다운로드 파일 일치(필기가 포함된 상태에서도, 카드2 회귀 확인) ----
        with page.expect_download() as dl:
            page.click("button:has-text('1:1 PNG 다운로드')")
        dl_path = os.path.join(ASSETS, "downloads", "ink-1-1.png")
        dl.value.save_as(dl_path)
        with open(dl_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        results.append({
            "id": "INK-download-match",
            "desc": "필기 포함 상태에서도 미리보기==다운로드 파일 일치",
            "result": "PASS" if file_hash == after_on else "FAIL",
        })

        # ---- 5) 두 번째 스트로크 추가 후 실행취소 -> 첫 스트로크 상태로 정확히 복귀 ----
        stroke2 = [(0.6, 0.6, 0.5), (0.65, 0.65, 0.9), (0.7, 0.6, 0.5)]
        dispatch_pen_stroke(page, "canvas-1x1", stroke2, pointer_id=202)
        page.wait_for_timeout(150)
        after_two_strokes = canvas_hash(page, "canvas-1x1")
        page.click("#inkUndoBtn")
        page.wait_for_timeout(150)
        after_undo = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "INK-undo",
            "desc": "필기 실행취소 -> 직전(스트로크 1개) 상태와 픽셀 동일",
            "result": "PASS" if (after_two_strokes != after_on and after_undo == after_on) else "FAIL",
        })

        # ---- 6) 전체 지우기 -> 필기 이전(문구만 있는) 상태와 동일 ----
        page.click("#inkClearBtn")
        page.wait_for_timeout(150)
        after_clear = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "INK-clear",
            "desc": "필기 전체 지우기 -> 필기 시작 전 상태와 픽셀 동일",
            "result": "PASS" if after_clear == before_on else "FAIL",
        })
        page.screenshot(path=os.path.join(RESULTS, "ink_after_clear.png"), full_page=True)

        # ---- 7) 편집 기록에 필기 관련 항목이 순서대로 쌓였는지 ----
        labels = page.eval_on_selector_all(".history-item .h-label", "els => els.map(e => e.textContent)")
        has_add = any("손글씨 추가" in l for l in labels)
        has_undo = any("실행취소" in l for l in labels)
        has_clear = any("레이어 지우기" in l for l in labels)
        results.append({
            "id": "INK-history-log",
            "desc": "손글씨 추가/실행취소/레이어 지우기가 편집 기록에 순서대로 남음",
            "result": "PASS" if has_add and has_undo and has_clear else "FAIL",
            "labels": labels,
        })

        # ---- 8) 다시 그려서 템플릿으로 저장 -> 불러오기 -> 픽셀 동일 & JSON에 ink 레이어/fontFamily 포함 ----
        # 문구 레이어(1번 칩)를 선택해 글꼴을 바꾸고, 손글씨 레이어(2번 칩)를 다시 선택해 한 번 더 그린다.
        page.click(".layer-chip:nth-child(1)")
        page.wait_for_timeout(100)
        page.select_option("#fontFamily", "jua")
        page.wait_for_timeout(300)
        page.click(".layer-chip:nth-child(2)")
        page.wait_for_timeout(100)
        dispatch_pen_stroke(page, "canvas-1x1", stroke_points, pointer_id=203)
        page.wait_for_timeout(150)
        saved_hash = canvas_hash(page, "canvas-1x1")

        page.once("dialog", lambda d: d.accept("폰트+필기 템플릿"))
        page.click("#saveTemplateBtn")
        page.wait_for_timeout(150)

        with page.expect_download() as dl2:
            page.click("#exportJsonBtn")
        export_path = os.path.join(ASSETS, "downloads", "templates_with_ink.json")
        dl2.value.save_as(export_path)
        with open(export_path, encoding="utf-8") as f:
            exported = json.load(f)
        last = exported[-1]
        layers = last.get("layers") or []
        text_layer = next((l for l in layers if l.get("type") != "ink"), {})
        ink_layer = next((l for l in layers if l.get("type") == "ink"), {})
        has_fields = (
            text_layer.get("fontFamily") == "jua"
            and isinstance(ink_layer.get("strokes"), dict)
            and len(ink_layer["strokes"].get("1:1", [])) > 0
        )
        results.append({
            "id": "TEMPLATE-export-fields",
            "desc": "내보낸 JSON에 문구 레이어의 fontFamily와 손글씨 레이어의 strokes가 그대로 담김",
            "result": "PASS" if has_fields else "FAIL",
        })

        # 초기화 후 다시 불러와서 픽셀이 저장 시점과 같은지(문구 레이어로 돌아가서 값을 바꿔본다)
        page.click(".layer-chip:nth-child(1)")
        page.wait_for_timeout(100)
        page.fill("#textInput", "임시로 바꿔봄")
        page.select_option("#fontFamily", "default")
        page.wait_for_timeout(300)
        page.click(".template-item:last-child button:has-text('불러오기')")
        page.wait_for_timeout(300)
        reloaded_hash = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "TEMPLATE-roundtrip",
            "desc": "템플릿 저장 -> 다른 걸로 바꿈 -> 다시 불러오기 -> 저장 시점과 픽셀 동일(글꼴+필기 포함)",
            "result": "PASS" if reloaded_hash == saved_hash else "FAIL",
        })
        page.screenshot(path=os.path.join(RESULTS, "font_ink_template_roundtrip.png"), full_page=True)

        b.close()
    httpd.shutdown()

    with open(os.path.join(RESULTS, "log_font_ink.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    for r in results:
        print("-", r["id"], r["desc"], "=>", r["result"])
    fails = [r for r in results if r["result"] != "PASS"]
    print("\n총", len(results), "건,", len(fails), "건 실패")


if __name__ == "__main__":
    main()
