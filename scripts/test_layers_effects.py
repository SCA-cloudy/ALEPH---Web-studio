"""문구 레이어(복사/삭제), 회전·그림자·네온 효과, '+' 기능 추가 UI, 템플릿 패널 우측 이동 검증."""
import base64
import hashlib
import http.server
import os
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(__file__), "..")
ASSETS = os.path.join(ROOT, "test-assets")
RESULTS = os.path.join(ASSETS, "results")
DOWNLOADS = os.path.join(ASSETS, "downloads")
PORT = 8917


def start_server():
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), http.server.SimpleHTTPRequestHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def canvas_hash(page, canvas_id):
    data_url = page.eval_on_selector(f"#{canvas_id}", "el => el.toDataURL('image/png')")
    return hashlib.sha256(base64.b64decode(data_url.split(",", 1)[1])).hexdigest()


def set_range_final(page, sel, value):
    page.eval_on_selector(
        sel,
        "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
        value,
    )
    page.wait_for_timeout(80)


def main():
    httpd = start_server()
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1100})
        page.goto(f"http://127.0.0.1:{PORT}/index.html")
        page.wait_for_timeout(200)
        page.set_input_files("#fileInput", os.path.join(ASSETS, "sample_landscape.jpg"))
        page.wait_for_timeout(150)
        page.fill("#textInput", "메인 문구")
        page.wait_for_timeout(150)

        # ---- 0) 기본 화면은 덜 복잡해야 한다: 효과 블록이 기본적으로 숨겨져 있는지 ----
        hidden0 = page.eval_on_selector_all(
            "#featureMenu,#rotationBlock,#shadowBlock,#neonBlock",
            "els => els.every(e => e.hidden)"
        )
        results.append({"id": "DECLUTTER-default-hidden", "desc": "+ 기능 추가 메뉴/효과 블록이 기본적으로 접혀 있음", "result": "PASS" if hidden0 else "FAIL"})

        # ---- 0b) 손글씨는 별도의 문구 레이어(입력 방식)로 존재: 손글씨 레이어를 고르면
        #          문구 컨트롤 대신 손글씨(펜) 컨트롤이 나타난다 ----
        page.click("#addInkLayerBtn")
        page.wait_for_timeout(80)
        ink_controls_visible = page.eval_on_selector("#inkLayerControls", "el => !el.hidden")
        text_controls_hidden = page.eval_on_selector("#textLayerControls", "el => el.hidden")
        results.append({
            "id": "INPUT-METHOD-ink-layer",
            "desc": "'+ 손글씨'로 손글씨 레이어를 추가하면 2.문구 영역이 손글씨(펜) 입력 방식으로 바뀜",
            "result": "PASS" if ink_controls_visible and text_controls_hidden else "FAIL",
        })

        # ---- 0c) 감압 펜뿐 아니라 "마우스 클릭 + 드래그"만으로도 그려지는지(실제 브라우저 mouse API 사용) ----
        before_mouse = canvas_hash(page, "canvas-1x1")
        box = page.eval_on_selector(
            "#canvas-1x1", "el => { const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; }"
        )
        page.mouse.move(box["x"] + box["w"] * 0.2, box["y"] + box["h"] * 0.3)
        page.mouse.down()
        page.mouse.move(box["x"] + box["w"] * 0.4, box["y"] + box["h"] * 0.25, steps=5)
        page.mouse.move(box["x"] + box["w"] * 0.5, box["y"] + box["h"] * 0.35, steps=5)
        page.mouse.up()
        page.wait_for_timeout(150)
        after_mouse = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "INK-mouse-drag",
            "desc": "펜/터치 없이 마우스 클릭+드래그만으로도 손글씨 레이어에 그려짐",
            "result": "PASS" if before_mouse != after_mouse else "FAIL",
        })

        page.click("#delLayerBtn")  # 다시 문구 레이어만 남기고 이후 테스트 진행
        page.wait_for_timeout(80)

        page.click("#featureMenuBtn")
        page.wait_for_timeout(80)
        menu_visible = page.eval_on_selector("#featureMenu", "el => !el.hidden")
        results.append({"id": "DECLUTTER-menu-open", "desc": "'+ 기능 추가' 클릭 시 메뉴가 펼쳐짐", "result": "PASS" if menu_visible else "FAIL"})

        # ---- 1) 템플릿 패널이 우측(aside.templates)으로 이동했는지 구조 확인 ----
        parent_class = page.eval_on_selector("#saveTemplateBtn", "el => el.closest('aside.templates') ? 'aside' : (el.closest('section.controls') ? 'controls' : 'other')")
        results.append({"id": "TEMPLATE-panel-right", "desc": "템플릿 저장/업데이트/내보내기/가져오기가 좌측이 아닌 우측(aside)에 있음", "result": "PASS" if parent_class == "aside" else "FAIL"})

        # ---- 2) 회전: 켜면 컨트롤이 보이고, 각도를 바꾸면 실제로 렌더가 바뀜 ----
        page.check("#featRotation")
        page.wait_for_timeout(80)
        rot_visible = page.eval_on_selector("#rotationBlock", "el => !el.hidden")
        before_rot = canvas_hash(page, "canvas-1x1")
        set_range_final(page, "#rotation", -25)
        after_rot = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "ROTATION",
            "desc": "회전 체크 시 컨트롤 노출 + 각도 변경 시 렌더 반영",
            "result": "PASS" if rot_visible and before_rot != after_rot else "FAIL",
        })
        set_range_final(page, "#rotation", 0)  # 이후 테스트에 영향 없도록 원위치

        # ---- 3) 그림자: 켜면 픽셀이 바뀌고, 끄면 원래대로(거의) 돌아옴 ----
        before_shadow = canvas_hash(page, "canvas-1x1")
        page.check("#featShadow")
        page.wait_for_timeout(80)
        shadow_visible = page.eval_on_selector("#shadowBlock", "el => !el.hidden")
        after_shadow_on = canvas_hash(page, "canvas-1x1")
        page.uncheck("#featShadow")
        page.wait_for_timeout(80)
        after_shadow_off = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "SHADOW",
            "desc": "그림자 체크 시 컨트롤 노출 + 픽셀 변화, 해제 시 원상태로 복귀",
            "result": "PASS" if shadow_visible and after_shadow_on != before_shadow and after_shadow_off == before_shadow else "FAIL",
        })

        # ---- 4) 네온: 켜면 픽셀이 바뀜 ----
        before_neon = canvas_hash(page, "canvas-1x1")
        page.check("#featNeon")
        page.wait_for_timeout(80)
        neon_visible = page.eval_on_selector("#neonBlock", "el => !el.hidden")
        after_neon = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "NEON",
            "desc": "네온 체크 시 컨트롤 노출 + 픽셀 변화(발광 효과 적용)",
            "result": "PASS" if neon_visible and after_neon != before_neon else "FAIL",
        })
        page.uncheck("#featNeon")
        page.wait_for_timeout(80)

        page.screenshot(path=os.path.join(RESULTS, "effects_demo.png"), full_page=True)

        # ---- 5) 문구 레이어 복사(+ 복사) : 독립적으로 편집되는지 ----
        chip_count_before = page.eval_on_selector_all(".layer-chip", "els => els.length")
        page.click("#dupLayerBtn")
        page.wait_for_timeout(120)
        chip_count_after = page.eval_on_selector_all(".layer-chip", "els => els.length")
        # 복사된(현재 활성) 레이어의 문구를 다르게 바꾼다.
        page.fill("#textInput", "두 번째(복사된) 문구")
        page.wait_for_timeout(120)
        # 첫 번째 칩을 눌러 원래 레이어로 돌아가면 문구가 "메인 문구" 그대로여야 한다(독립적으로 관리됨).
        page.click(".layer-chip:nth-child(1)")
        page.wait_for_timeout(120)
        first_layer_text = page.eval_on_selector("#textInput", "el => el.value")
        page.click(".layer-chip:nth-child(2)")
        page.wait_for_timeout(120)
        second_layer_text = page.eval_on_selector("#textInput", "el => el.value")
        results.append({
            "id": "LAYER-duplicate-independent",
            "desc": "레이어 복사 후 각 레이어의 문구가 서로 독립적으로 유지됨",
            "result": "PASS" if (
                chip_count_after == chip_count_before + 1
                and first_layer_text == "메인 문구"
                and second_layer_text == "두 번째(복사된) 문구"
            ) else "FAIL",
        })

        # 두 레이어 모두 있을 때 미리보기==다운로드 파일 일치(회귀 확인, 회전 등과 함께 있어도 유지되는지)
        multi_hash = canvas_hash(page, "canvas-1x1")
        with page.expect_download() as dl:
            page.click("button:has-text('1:1 PNG 다운로드')")
        dl_path = os.path.join(DOWNLOADS, "multilayer-1-1.png")
        dl.value.save_as(dl_path)
        with open(dl_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        results.append({
            "id": "LAYER-multi-download-match",
            "desc": "문구 레이어 2개 상태에서도 미리보기==다운로드 파일 일치",
            "result": "PASS" if multi_hash == file_hash else "FAIL",
        })
        page.screenshot(path=os.path.join(RESULTS, "two_layers_demo.png"), full_page=True)

        # ---- 6) 레이어 삭제: 1개 남으면 삭제 버튼 비활성화 ----
        page.click("#delLayerBtn")  # 현재 활성(2번째) 레이어 삭제
        page.wait_for_timeout(120)
        chip_count_final = page.eval_on_selector_all(".layer-chip", "els => els.length")
        del_disabled = page.eval_on_selector("#delLayerBtn", "el => el.disabled")
        results.append({
            "id": "LAYER-delete",
            "desc": "레이어 삭제 후 1개 남으면 삭제 버튼이 비활성화됨",
            "result": "PASS" if chip_count_final == 1 and del_disabled else "FAIL",
        })

        # ---- 7) 위치(가로/세로) 슬라이더가 조작 패널이 아니라 미리보기 아래 "위치" 패널에 있음 ----
        pos_panel_in_center = page.eval_on_selector(
            "#positionPanel",
            "el => el.closest('.center-col') !== null && el.previousElementSibling?.classList.contains('previews')",
        )
        posx_outside_controls = page.eval_on_selector(
            "#posX", "el => el.closest('.controls') === null"
        )
        results.append({
            "id": "POSITION-panel-in-preview-column",
            "desc": "가로·세로 위치 슬라이더가 좌측 조작 패널이 아니라 가운데 미리보기 바로 아래 '위치' 패널에 있음",
            "result": "PASS" if pos_panel_in_center and posx_outside_controls else "FAIL",
        })

        # ---- 8) 위치 패널이 레이어 종류에 맞춰 바뀜(문구->도형->손글씨) ----
        text_pos_visible = page.eval_on_selector("#positionControlsText", "el => !el.hidden")
        page.click("#addShapeLayerBtn")
        page.wait_for_timeout(100)
        shape_pos_visible = page.eval_on_selector("#positionControlsShape", "el => !el.hidden")
        text_pos_hidden_on_shape = page.eval_on_selector("#positionControlsText", "el => el.hidden")
        page.click("#addInkLayerBtn")
        page.wait_for_timeout(100)
        none_note_visible = page.eval_on_selector("#positionPanelNone", "el => !el.hidden")
        results.append({
            "id": "POSITION-panel-switches-with-layer-type",
            "desc": "'위치' 패널이 문구/도형 선택 시 각각의 위치 슬라이더로, 손글씨 선택 시 안내 문구로 바뀜",
            "result": "PASS" if (text_pos_visible and shape_pos_visible and text_pos_hidden_on_shape and none_note_visible) else "FAIL",
        })
        page.click("#delLayerBtn")  # 손글씨 레이어 정리
        page.wait_for_timeout(80)
        page.click("#delLayerBtn")  # 도형 레이어 정리
        page.wait_for_timeout(80)

        # ---- 9) 위치 패널의 슬라이더를 움직여도 여전히 렌더에 반영됨(자리만 옮겼지 동작은 그대로) ----
        before_move = canvas_hash(page, "canvas-1x1")
        set_range_final(page, "#posX", 12)
        after_move = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "POSITION-panel-still-updates-canvas",
            "desc": "옮긴 위치 슬라이더를 움직이면 지금까지처럼 캔버스에 바로 반영됨",
            "result": "PASS" if before_move != after_move else "FAIL",
        })
        set_range_final(page, "#posX", 50)  # 원위치

        b.close()
    httpd.shutdown()

    for r in results:
        print("-", r["id"], r["desc"], "=>", r["result"])
    fails = [r for r in results if r["result"] != "PASS"]
    print("\n총", len(results), "건,", len(fails), "건 실패")


if __name__ == "__main__":
    main()
