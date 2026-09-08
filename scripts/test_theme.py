"""라이트/다크 테마 토글 검증(앱 UI에만 적용되고, 캔버스 결과물 픽셀에는 영향 없음)."""
import hashlib
import base64
import http.server
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
PORT = 8981


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def canvas_hash(page, canvas_id):
    data_url = page.eval_on_selector(f"#{canvas_id}", "el => el.toDataURL('image/png')")
    return hashlib.sha256(base64.b64decode(data_url.split(",", 1)[1])).hexdigest()


def main():
    httpd = start_server()
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(f"http://127.0.0.1:{PORT}/index.html")
        page.wait_for_timeout(200)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        page.fill("#textInput", "테마 테스트")
        page.wait_for_timeout(150)

        # ---- 1) 기본은 라이트 테마 ----
        initial_theme = page.eval_on_selector(":root", "el => document.documentElement.dataset.theme")
        light_active = page.eval_on_selector("#themeLightBtn", "el => el.classList.contains('active')")
        results.append({
            "id": "THEME-default-light",
            "desc": "처음 방문 시(저장된 설정 없음) 기본은 라이트 테마이고 '라이트' 버튼이 활성 표시됨",
            "result": "PASS" if initial_theme == "light" and light_active else "FAIL",
        })

        canvas_hash_before = canvas_hash(page, "canvas-1x1")

        # ---- 2) '다크' 클릭 -> data-theme 전환 + 버튼 활성 표시 전환 ----
        page.click("#themeDarkBtn")
        page.wait_for_timeout(100)
        theme_after_click = page.eval_on_selector(":root", "el => document.documentElement.dataset.theme")
        dark_active = page.eval_on_selector("#themeDarkBtn", "el => el.classList.contains('active')")
        light_inactive = page.eval_on_selector("#themeLightBtn", "el => !el.classList.contains('active')")
        results.append({
            "id": "THEME-switch-to-dark",
            "desc": "'다크' 버튼 클릭 시 data-theme=dark 로 바뀌고 '다크' 버튼만 활성 표시됨",
            "result": "PASS" if theme_after_click == "dark" and dark_active and light_inactive else "FAIL",
        })

        # ---- 3) 앱 UI 색은 바뀌지만, 미리보기 캔버스(결과물) 픽셀은 그대로 ----
        panel_bg_dark = page.eval_on_selector(
            ".panel", "el => getComputedStyle(el).backgroundColor"
        )
        canvas_hash_after = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "THEME-canvas-unaffected",
            "desc": "테마를 바꿔도 미리보기 캔버스(합성 결과물) 픽셀은 그대로 유지됨(앱 UI에만 적용)",
            "result": "PASS" if canvas_hash_after == canvas_hash_before else "FAIL",
            "panel_bg_dark": panel_bg_dark,
        })

        # ---- 4) localStorage에 저장되어 새로고침해도 유지됨 ----
        stored = page.evaluate("() => localStorage.getItem('meme-card-theme-v1')")
        page.reload()
        page.wait_for_timeout(200)
        theme_after_reload = page.eval_on_selector(":root", "el => document.documentElement.dataset.theme")
        dark_active_after_reload = page.eval_on_selector("#themeDarkBtn", "el => el.classList.contains('active')")
        results.append({
            "id": "THEME-persist-reload",
            "desc": "다크 테마 선택은 이 브라우저에 저장되어 새로고침 후에도 유지됨",
            "result": "PASS" if stored == "dark" and theme_after_reload == "dark" and dark_active_after_reload else "FAIL",
        })

        # ---- 5) 다시 라이트로 전환 가능 ----
        page.click("#themeLightBtn")
        page.wait_for_timeout(100)
        theme_back_to_light = page.eval_on_selector(":root", "el => document.documentElement.dataset.theme")
        results.append({
            "id": "THEME-switch-back-to-light",
            "desc": "'라이트' 버튼을 다시 누르면 라이트 테마로 되돌아감",
            "result": "PASS" if theme_back_to_light == "light" else "FAIL",
        })

        b.close()
    httpd.shutdown()

    for r in results:
        print("-", r["id"], r["desc"], "=>", r["result"])
    fails = [r for r in results if r["result"] != "PASS"]
    print("\n총", len(results), "건,", len(fails), "건 실패")


if __name__ == "__main__":
    main()
