"""손글씨 인식(OCR, Tesseract.js) -> 문구 레이어 변환 기능 검증.

이 개발 샌드박스는 외부 네트워크가 허용 목록 방식이라 Tesseract.js를 불러오는
jsdelivr(cdn.jsdelivr.net)로의 요청이 막혀 있다(curl 결과 403 Forbidden, 글꼴 때와 동일한 제약).
그래서 여기서는 "엔진을 못 불러왔을 때 앱이 죽지 않고 안내 메시지를 보여준 뒤 계속 쓸 수 있는지"와
"손글씨가 없는 상태에서 누르면 적절히 안내하는지"를 검증한다. 실제 GitHub Pages 배포 환경에서는
방문자 브라우저가 일반적인 인터넷 환경이라 엔진이 정상적으로 로드되어 인식까지 이어진다.
"""
import http.server
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
RESULTS = os.path.join(ASSETS, "results")
PORT = 8944


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def dispatch_pen_stroke(page, canvas_id, points, pointer_id=301):
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


TESSERACT_STUB = """
window.__ocrCalls = [];
window.Tesseract = {
  recognize: (dataUrl, lang) => {
    window.__ocrCalls.push(lang);
    return Promise.resolve({ data: { text: `stub:${lang}` } });
  },
};
"""


def main():
    httpd = start_server()
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"http://127.0.0.1:{PORT}/index.html")
        page.wait_for_timeout(300)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)

        # ---- 1) 버튼이 손글씨 레이어 컨트롤 안에 있고, 문구 레이어에서는 안 보임 ----
        text_layer_hidden = page.eval_on_selector("#inkLayerControls", "el => el.hidden")
        results.append({
            "id": "OCR-button-scoped-to-ink-layer",
            "desc": "문구 레이어가 선택된 기본 상태에서는 손글씨 인식 버튼(inkLayerControls 안)이 숨어 있음",
            "result": "PASS" if text_layer_hidden else "FAIL",
        })

        page.click("#addInkLayerBtn")
        page.wait_for_timeout(100)
        btn_visible = page.eval_on_selector("#inkRecognizeBtn", "el => !el.closest('#inkLayerControls').hidden")
        results.append({
            "id": "OCR-button-visible-on-ink-layer",
            "desc": "손글씨 레이어 선택 시 '손글씨 인식 → 문구로 변환' 버튼이 보임",
            "result": "PASS" if btn_visible else "FAIL",
        })

        # ---- 2) 손글씨가 하나도 없는 상태에서 누르면 앱이 죽지 않고 안내 메시지를 보여줌 ----
        page.click("#inkRecognizeBtn")
        page.wait_for_timeout(200)
        empty_msg = page.eval_on_selector("#inkRecognizeStatus", "el => el.hidden ? null : el.textContent")
        results.append({
            "id": "OCR-empty-ink-guard",
            "desc": "손글씨 없이 인식 버튼을 누르면 죽지 않고 안내 메시지가 뜸",
            "result": "PASS" if empty_msg and "없습니다" in empty_msg else "FAIL",
            "message": empty_msg,
        })

        # ---- 3) 손글씨를 그린 뒤 인식 버튼을 누르면(이 샌드박스는 엔진 CDN이 막혀 있어 실패 경로를 탐) ----
        #     엔진 로드 실패든 인식 실패든, 앱이 멈추지 않고 사용자에게 원인을 알리는 메시지를 보여주고
        #     버튼은 다시 눌러볼 수 있는 상태(disabled 해제)로 돌아와야 한다.
        dispatch_pen_stroke(page, "canvas-1x1", [(0.2, 0.3, 0.6), (0.3, 0.25, 0.6), (0.4, 0.32, 0.6), (0.5, 0.28, 0.6)])
        page.wait_for_timeout(150)
        page.click("#inkRecognizeBtn")
        # 엔진 로드/네트워크 타임아웃까지 기다려준다(최대 8초).
        page.wait_for_function(
            "() => !document.querySelector('#inkRecognizeStatus').hidden && document.querySelector('#inkRecognizeStatus').textContent.length > 0",
            timeout=8000,
        )
        msg = page.eval_on_selector("#inkRecognizeStatus", "el => el.textContent")
        btn_disabled_after = page.eval_on_selector("#inkRecognizeBtn", "el => el.disabled")
        app_alive = page.eval_on_selector("#addInkLayerBtn", "el => !!el") is True
        results.append({
            "id": "OCR-graceful-failure",
            "desc": "이 샌드박스는 인식 엔진 CDN이 막혀 있어 실패하지만, 죽지 않고 안내 메시지를 보여주며 버튼이 다시 사용 가능한 상태로 돌아옴",
            "result": "PASS" if msg and not btn_disabled_after and app_alive else "FAIL",
            "message": msg,
        })
        page.screenshot(path=os.path.join(RESULTS, "ocr_graceful_failure.png"), full_page=True)

        # ---- 4) 레이어를 바꾸면 이전 인식 결과/오류 메시지가 지워짐 ----
        page.click("#addInkLayerBtn")  # 새 손글씨 레이어로 전환
        page.wait_for_timeout(100)
        status_cleared = page.eval_on_selector("#inkRecognizeStatus", "el => el.hidden")
        results.append({
            "id": "OCR-status-clears-on-layer-switch",
            "desc": "레이어를 바꾸면 이전 인식 상태 메시지가 사라짐",
            "result": "PASS" if status_cleared else "FAIL",
        })

        # ---- 5) 언어 선택 드롭다운의 기본값은 "한국어+영어" ----
        default_lang = page.eval_on_selector("#inkRecognizeLang", "el => el.value")
        results.append({
            "id": "OCR-lang-default",
            "desc": "인식 언어 드롭다운의 기본값이 '한국어+영어'(kor+eng)임",
            "result": "PASS" if default_lang == "kor+eng" else "FAIL",
            "default_lang": default_lang,
        })

        # ---- 6) 실제 CDN이 막혀 있어 진짜 인식은 못 해보니, Tesseract를 가짜로 심어서
        #         "선택한 언어가 그대로 Tesseract.recognize()에 전달되는지"만 따로 검증한다. ----
        page.evaluate(TESSERACT_STUB)
        dispatch_pen_stroke(page, "canvas-1x1", [(0.2, 0.3, 0.6), (0.3, 0.25, 0.6), (0.4, 0.32, 0.6)])
        page.wait_for_timeout(100)
        page.select_option("#inkRecognizeLang", "jpn")
        page.click("#inkRecognizeBtn")
        page.wait_for_function(
            "() => window.__ocrCalls && window.__ocrCalls.length > 0", timeout=3000
        )
        calls = page.evaluate("() => window.__ocrCalls")
        new_layer_text = page.eval_on_selector_all(
            ".layer-chip", "els => els[els.length - 1].textContent"
        )
        results.append({
            "id": "OCR-lang-selection-passed-through",
            "desc": "드롭다운에서 고른 언어(예: 일본어)가 그대로 Tesseract.recognize()에 전달되고, 인식 결과가 새 문구 레이어에 담김",
            "result": "PASS" if calls == ["jpn"] and "jpn" in new_layer_text else "FAIL",
            "calls": calls, "new_layer_text": new_layer_text,
        })

        # ---- 7) 다른 언어(중국어 간체)로 바꿔도 그대로 전달됨 ----
        page.click("#addInkLayerBtn")
        page.wait_for_timeout(100)
        dispatch_pen_stroke(page, "canvas-1x1", [(0.2, 0.3, 0.6), (0.3, 0.25, 0.6), (0.4, 0.32, 0.6)])
        page.wait_for_timeout(100)
        page.select_option("#inkRecognizeLang", "chi_sim")
        page.click("#inkRecognizeBtn")
        page.wait_for_function(
            "() => window.__ocrCalls && window.__ocrCalls.length > 1", timeout=3000
        )
        calls2 = page.evaluate("() => window.__ocrCalls")
        results.append({
            "id": "OCR-lang-selection-switches",
            "desc": "언어를 다시 바꿔도(중국어 간체) 매번 그 선택이 그대로 전달됨",
            "result": "PASS" if calls2 == ["jpn", "chi_sim"] else "FAIL",
            "calls": calls2,
        })

        b.close()
    httpd.shutdown()

    for r in results:
        print("-", r["id"], r["desc"], "=>", r["result"])
    fails = [r for r in results if r["result"] != "PASS"]
    print("\n총", len(results), "건,", len(fails), "건 실패")


if __name__ == "__main__":
    main()
