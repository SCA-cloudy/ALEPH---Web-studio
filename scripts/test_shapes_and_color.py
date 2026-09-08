"""도형(하트/별/폭죽) 레이어 + 재사용 색상 컨트롤(HEX/RGB/그라데이션) 검증."""
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
DOWNLOADS = os.path.join(ASSETS, "downloads")
PORT = 8977


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


def set_input(page, sel, value, event="input"):
    page.eval_on_selector(
        sel,
        "(el, args) => { el.value = args.v; el.dispatchEvent(new Event(args.evt, {bubbles:true})); }",
        {"v": value, "evt": event},
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
        page.fill("#textInput", "도형 테스트")
        page.wait_for_timeout(150)

        # ---- 1) "+ 도형"으로 도형 레이어 추가 -> 컨트롤이 도형용으로 바뀜 ----
        page.click("#addShapeLayerBtn")
        page.wait_for_timeout(100)
        shape_controls_visible = page.eval_on_selector("#shapeLayerControls", "el => !el.hidden")
        text_controls_hidden = page.eval_on_selector("#textLayerControls", "el => el.hidden")
        results.append({
            "id": "SHAPE-controls-visible",
            "desc": "'+ 도형' 클릭 시 2.문구 영역이 도형 컨트롤(모양/색/위치/크기/회전)로 바뀜",
            "result": "PASS" if shape_controls_visible and text_controls_hidden else "FAIL",
        })

        # ---- 2) 도형 모양을 바꾸면(하트->별->폭죽) 픽셀이 각각 달라짐 ----
        hash_heart = canvas_hash(page, "canvas-1x1")
        page.select_option("#shapeKind", "star")
        page.wait_for_timeout(100)
        hash_star = canvas_hash(page, "canvas-1x1")
        page.select_option("#shapeKind", "firework")
        page.wait_for_timeout(100)
        hash_firework = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "SHAPE-kind-change",
            "desc": "도형 모양(하트/별/폭죽) 변경 시 서로 다른 픽셀로 렌더됨",
            "result": "PASS" if len({hash_heart, hash_star, hash_firework}) == 3 else "FAIL",
        })

        # ---- 3) 위치/크기/회전 슬라이더가 실제 렌더에 반영됨 ----
        before_size = canvas_hash(page, "canvas-1x1")
        set_range_final(page, "#shapeSize", 30)
        after_size = canvas_hash(page, "canvas-1x1")
        set_range_final(page, "#shapeRotation", 45)
        after_rot = canvas_hash(page, "canvas-1x1")
        set_range_final(page, "#shapeX", 20)
        set_range_final(page, "#shapeY", 20)
        after_pos = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "SHAPE-transform",
            "desc": "도형 크기/회전/위치 슬라이더가 각각 렌더에 반영됨",
            "result": "PASS" if before_size != after_size != after_rot != after_pos else "FAIL",
        })

        # ---- 4) 도형 색상 컨트롤: HEX 입력 -----
        page.click("#shapeColorControl .color-swatch")
        page.wait_for_timeout(80)
        before_hex = canvas_hash(page, "canvas-1x1")
        set_input(page, "#shapeColorControl .c-hex", "00ff00", "change")
        after_hex = canvas_hash(page, "canvas-1x1")
        rgb_synced = page.eval_on_selector_all(
            "#shapeColorControl .c-r, #shapeColorControl .c-g, #shapeColorControl .c-b",
            "els => els.map(e => e.value)"
        )
        results.append({
            "id": "SHAPE-color-hex",
            "desc": "도형 색상 컨트롤의 HEX 입력이 렌더에 반영되고 RGB 입력칸과 동기화됨",
            "result": "PASS" if before_hex != after_hex and rgb_synced == ["0", "255", "0"] else "FAIL",
            "rgb": rgb_synced,
        })

        # ---- 5) 도형 색상 컨트롤: RGB 입력 -----
        before_rgb = canvas_hash(page, "canvas-1x1")
        set_input(page, "#shapeColorControl .c-r", "10", "input")
        set_input(page, "#shapeColorControl .c-g", "20", "input")
        set_input(page, "#shapeColorControl .c-b", "230", "change")
        after_rgb = canvas_hash(page, "canvas-1x1")
        hex_synced = page.eval_on_selector("#shapeColorControl .c-hex", "el => el.value")
        results.append({
            "id": "SHAPE-color-rgb",
            "desc": "도형 색상 컨트롤의 RGB 입력이 렌더에 반영되고 HEX 입력칸과 동기화됨",
            "result": "PASS" if before_rgb != after_rgb and hex_synced == "0a14e6" else "FAIL",
            "hex": hex_synced,
        })

        # ---- 6) 도형 색상: 그라데이션 모드로 전환하면 픽셀이 바뀜 ----
        before_grad = canvas_hash(page, "canvas-1x1")
        page.click('#shapeColorControl [data-mode="gradient"]')
        page.wait_for_timeout(100)
        after_grad = canvas_hash(page, "canvas-1x1")
        grad_fields_visible = page.eval_on_selector("#shapeColorControl .color-gradient-fields", "el => !el.hidden")
        set_input(page, "#shapeColorControl .c-grad-angle", "200", "change")
        after_angle = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "SHAPE-color-gradient",
            "desc": "도형 색상을 그라데이션으로 바꾸면 필드가 나타나고 픽셀이 바뀌며, 각도 변경도 반영됨",
            "result": "PASS" if grad_fields_visible and before_grad != after_grad and after_grad != after_angle else "FAIL",
        })
        page.screenshot(path=os.path.join(RESULTS, "shape_gradient_demo.png"), full_page=True)

        # ---- 7) 문구 레이어 색상도 같은 컨트롤: 단색 -> 그라데이션 전환 시 픽셀 변화 ----
        page.click(".layer-chip:nth-child(1)")  # 원래 문구 레이어로 돌아가기
        page.wait_for_timeout(100)
        before_text_grad = canvas_hash(page, "canvas-1x1")
        page.click("#textColorControl .color-swatch")
        page.wait_for_timeout(80)
        page.click('#textColorControl [data-mode="gradient"]')
        page.wait_for_timeout(100)
        after_text_grad = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "TEXT-color-gradient",
            "desc": "문구 색상도 같은 컨트롤로 그라데이션 전환 가능(픽셀 변화 확인)",
            "result": "PASS" if before_text_grad != after_text_grad else "FAIL",
        })

        # ---- 8) 도형 포함 상태에서도 미리보기==다운로드 파일 일치(카드2 회귀 확인) ----
        combined_hash = canvas_hash(page, "canvas-1x1")
        with page.expect_download() as dl:
            page.click("button:has-text('1:1 PNG 다운로드')")
        dl_path = os.path.join(DOWNLOADS, "shape-gradient-1-1.png")
        dl.value.save_as(dl_path)
        with open(dl_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        results.append({
            "id": "SHAPE-download-match",
            "desc": "도형 + 그라데이션 문구가 함께 있어도 미리보기==다운로드 파일 일치",
            "result": "PASS" if combined_hash == file_hash else "FAIL",
        })

        # ---- 9) 템플릿 저장 -> 초기화 -> 불러오기 -> 도형/그라데이션 픽셀 동일 ----
        saved_hash = canvas_hash(page, "canvas-1x1")
        page.once("dialog", lambda d: d.accept("도형+그라데이션 템플릿"))
        page.click("#saveTemplateBtn")
        page.wait_for_timeout(150)

        with page.expect_download() as dl2:
            page.click("#exportJsonBtn")
        export_path = os.path.join(DOWNLOADS, "templates_with_shape.json")
        dl2.value.save_as(export_path)
        with open(export_path, encoding="utf-8") as f:
            exported = json.load(f)
        last = exported[-1]
        layers = last.get("layers") or []
        shape_layer = next((l for l in layers if l.get("type") == "shape"), {})
        text_layer = next((l for l in layers if l.get("type") not in ("shape", "ink")), {})
        shape_color = shape_layer.get("color")
        shape_ok = (
            shape_layer.get("shapeKind") == "firework"
            and isinstance(shape_color, dict)
            and shape_color.get("type") == "gradient"
        )
        text_grad_ok = isinstance(text_layer.get("color"), dict) and text_layer["color"].get("type") == "gradient"
        results.append({
            "id": "EXPORT-shape-and-gradient-fields",
            "desc": "내보낸 JSON에 도형 레이어(shapeKind/color)와 문구 레이어의 그라데이션 색상이 그대로 담김",
            "result": "PASS" if shape_ok and text_grad_ok else "FAIL",
            "shape_layer": shape_layer, "text_color": text_layer.get("color"),
        })

        page.click(".layer-chip:nth-child(1)")
        page.wait_for_timeout(80)
        page.fill("#textInput", "임시로 바꿔봄")
        page.wait_for_timeout(150)
        page.click(".template-item:last-child button:has-text('불러오기')")
        page.wait_for_timeout(250)
        reloaded_hash = canvas_hash(page, "canvas-1x1")
        results.append({
            "id": "TEMPLATE-shape-roundtrip",
            "desc": "템플릿 저장 -> 다른 걸로 바꿈 -> 다시 불러오기 -> 저장 시점과 픽셀 동일(도형+그라데이션 포함)",
            "result": "PASS" if reloaded_hash == saved_hash else "FAIL",
        })

        # ---- 10) 도형 레이어 복사/삭제도 일반 레이어와 동일하게 동작 ----
        chip_count_before = page.eval_on_selector_all(".layer-chip", "els => els.length")
        shape_chip_idx = page.eval_on_selector_all(
            ".layer-chip", "els => els.findIndex(e => e.textContent.includes('✨'))"
        )
        page.click(f".layer-chip:nth-child({shape_chip_idx + 1})")
        page.wait_for_timeout(80)
        page.click("#dupLayerBtn")
        page.wait_for_timeout(100)
        chip_count_after_dup = page.eval_on_selector_all(".layer-chip", "els => els.length")
        page.click("#delLayerBtn")
        page.wait_for_timeout(100)
        chip_count_after_del = page.eval_on_selector_all(".layer-chip", "els => els.length")
        results.append({
            "id": "SHAPE-duplicate-delete",
            "desc": "도형 레이어도 '+ 복사'/삭제가 문구·손글씨 레이어와 동일하게 동작함",
            "result": "PASS" if chip_count_after_dup == chip_count_before + 1 and chip_count_after_del == chip_count_before else "FAIL",
        })

        b.close()
    httpd.shutdown()

    for r in results:
        print("-", r["id"], r["desc"], "=>", r["result"])
    fails = [r for r in results if r["result"] != "PASS"]
    print("\n총", len(results), "건,", len(fails), "건 실패")


if __name__ == "__main__":
    main()
