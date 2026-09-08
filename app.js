/* Quiplet — 짤·카드 스튜디오
 * 모든 처리는 브라우저 내부에서만 이루어지며 서버 전송이 없습니다.
 */

const RATIOS = [
  { key: "1:1", w: 1080, h: 1080, label: "1:1" },
  { key: "4:5", w: 1080, h: 1350, label: "4:5" },
  { key: "9:16", w: 1080, h: 1920, label: "9:16" },
];

const TEMPLATE_STORAGE_KEY = "meme-card-templates-v1";
const EMOJI_TAIL = '"Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji"';
const FONT_STACK = `${EMOJI_TAIL},"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR","Segoe UI",sans-serif`;

/** 글꼴 선택지: value -> 실제 사용할 CSS font-family (구글 폰트 + 이모지/한글 폴백) */
const FONT_OPTIONS = {
  default: { weight: 700, stack: `"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",${EMOJI_TAIL},sans-serif` },
  notosans: { weight: 700, stack: `"Noto Sans KR",${EMOJI_TAIL},sans-serif` },
  blackhan: { weight: 400, stack: `"Black Han Sans",${EMOJI_TAIL},sans-serif` },
  jua: { weight: 400, stack: `"Jua",${EMOJI_TAIL},sans-serif` },
  dohyeon: { weight: 400, stack: `"Do Hyeon",${EMOJI_TAIL},sans-serif` },
  gaegu: { weight: 700, stack: `"Gaegu",${EMOJI_TAIL},sans-serif` },
  pen: { weight: 400, stack: `"Nanum Pen Script",${EMOJI_TAIL},cursive,sans-serif` },
  poorstory: { weight: 400, stack: `"Poor Story",${EMOJI_TAIL},sans-serif` },
};

function fontDeclaration(fontFamilyKey, px) {
  const opt = FONT_OPTIONS[fontFamilyKey] || FONT_OPTIONS.default;
  return `${opt.weight} ${px}px ${opt.stack}`;
}

// ---------- 문구 레이어 ----------

/** 레이어는 세 종류: "text"(타이핑) / "ink"(손글씨·그림, 직접 그려서 넣는 입력 방식) /
 *  "shape"(하트·별·폭죽 같은 장식 벡터 도형). */
function makeLayer(overrides) {
  overrides = overrides || {};
  if (overrides.type === "ink") {
    return Object.assign(
      {
        id: uid(),
        type: "ink",
        penColor: "#ff2d55",
        penWidth: 6,
        // 비율(ratioKey)별 획. 각 획은 {x,y,pressure} 점의 배열이며
        // 캔버스 내부 픽셀 좌표(해당 비율의 실제 출력 해상도 기준)로 저장한다.
        strokes: { "1:1": [], "4:5": [], "9:16": [] },
      },
      overrides
    );
  }
  if (overrides.type === "shape") {
    return Object.assign(
      {
        id: uid(),
        type: "shape",
        shapeKind: "heart", // "heart" | "star" | "firework"
        color: "#ff4d6d", // 단색 "#rrggbb" 또는 그라데이션 {type:"gradient", from, to, angle}
        x: 50,
        y: 50,
        size: 14, // h 대비 %
        rotation: 0,
      },
      overrides
    );
  }
  return Object.assign(
    {
      id: uid(),
      type: "text",
      text: "",
      x: 50, // 0-100, 가로 중심 위치(%)
      y: 85, // 0-100, 세로 중심 위치(%)
      fontSize: 8, // h 대비 %
      color: "#ffffff", // 단색 "#rrggbb" 또는 그라데이션 {type:"gradient", from, to, angle}
      fontFamily: "default",
      stroke: true,
      rotation: 0, // -180 ~ 180도. 0이면 회전 없음.
      shadow: { enabled: false, color: "#000000", blur: 10 },
      neon: { enabled: false, color: "#00eaff" },
    },
    overrides
  );
}

/** 현재 편집 상태 */
const state = {
  image: null, // HTMLImageElement | null
  imageName: "",
  layers: [makeLayer({ type: "text" })],
  activeLayerId: null, // init()에서 첫 레이어로 설정
};
state.activeLayerId = state.layers[0].id;

function getActiveLayer() {
  return state.layers.find((l) => l.id === state.activeLayerId) || state.layers[0];
}

let textColorControl = null; // bindControls()에서 생성되는 재사용 색상 컨트롤 인스턴스
let shapeColorControl = null;

let currentTemplateId = null; // 현재 불러온 템플릿 id (없으면 신규)
let templates = loadTemplates();

/** 편집 기록(히스토리) — 새로고침하면 초기화되는 세션 한정 기록. localStorage에 저장하지 않음. */
let history = []; // { id, label, time, snapshot }
let historyIndex = -1; // 현재 위치(-1: 기록 없음)
const HISTORY_LIMIT = 40;

function debounce(fn, wait) {
  let t = null;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

// ---------- 유틸 ----------

function $(id) {
  return document.getElementById(id);
}

function uid() {
  return "t_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
}

function deepClone(v, fallback) {
  try {
    return JSON.parse(JSON.stringify(v));
  } catch (e) {
    return fallback;
  }
}

function cloneLayers(layers) {
  return deepClone(layers, [makeLayer({})]);
}

function loadTemplates() {
  try {
    const raw = localStorage.getItem(TEMPLATE_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    return [];
  }
}

function saveTemplatesToStorage() {
  localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
}

// ---------- 파일(이미지) 검증 및 로드 ----------

const PNG_SIG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const JPEG_SIG = [0xff, 0xd8, 0xff];

function sniffImageType(bytes) {
  if (PNG_SIG.every((b, i) => bytes[i] === b)) return "png";
  if (JPEG_SIG.every((b, i) => bytes[i] === b)) return "jpeg";
  return null;
}

function showFileError(msg) {
  const el = $("fileError");
  el.textContent = msg;
  el.hidden = false;
}
function clearFileError() {
  $("fileError").hidden = true;
}

function handleFile(file) {
  clearFileError();
  const reader = new FileReader();
  reader.onload = () => {
    const bytes = new Uint8Array(reader.result).slice(0, 8);
    const type = sniffImageType(bytes);
    if (!type) {
      showFileError(
        `지원하지 않는 파일입니다: "${file.name}". PNG 또는 JPEG 파일만 불러올 수 있어요. (기존 작업은 그대로 유지됩니다)`
      );
      return;
    }
    const blob = new Blob([reader.result], { type: type === "png" ? "image/png" : "image/jpeg" });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      state.image = img;
      state.imageName = file.name;
      $("fileInfo").textContent = `불러온 이미지: ${file.name} (${img.naturalWidth}×${img.naturalHeight}, ${type.toUpperCase()})`;
      renderAll();
      recordHistory(`이미지 불러옴: ${file.name}`);
    };
    img.onerror = () => {
      showFileError(`파일을 이미지로 열 수 없습니다: "${file.name}". (기존 작업은 그대로 유지됩니다)`);
    };
    img.src = url;
  };
  reader.onerror = () => {
    showFileError(`파일을 읽는 중 오류가 발생했습니다: "${file.name}". (기존 작업은 그대로 유지됩니다)`);
  };
  reader.readAsArrayBuffer(file);
}

// ---------- 텍스트 줄바꿈 ----------

/** 문자열을 코드포인트 단위 배열로 (대부분의 이모지를 한 단위로 처리) */
function toUnits(str) {
  return Array.from(str);
}

function isAsciiWordChar(ch) {
  return /[A-Za-z0-9'’-]/.test(ch);
}

/** 한 단락을 maxWidth에 맞게 줄바꿈. 한글 등은 글자 단위, 영문은 단어 단위로 끊는다. */
function wrapParagraph(ctx, paragraph, maxWidth) {
  if (paragraph === "") return [""];
  const units = toUnits(paragraph);
  // 토큰화: 연속된 ascii 단어문자는 하나의 토큰, 공백은 별도 토큰, 그 외는 글자 단위 토큰
  const tokens = [];
  let buf = "";
  for (const ch of units) {
    if (isAsciiWordChar(ch)) {
      buf += ch;
    } else {
      if (buf) {
        tokens.push(buf);
        buf = "";
      }
      tokens.push(ch);
    }
  }
  if (buf) tokens.push(buf);

  // 토큰 자체가 maxWidth보다 넓으면(끊어쓰기 없는 매우 긴 단어) 글자 단위로 강제 분해한다.
  // 이렇게 하지 않으면 프레임 바깥으로 문구가 잘려 나가 보이지 않게 된다.
  const expandedTokens = [];
  for (const tok of tokens) {
    if (tok.length > 1 && ctx.measureText(tok).width > maxWidth) {
      expandedTokens.push(...toUnits(tok));
    } else {
      expandedTokens.push(tok);
    }
  }

  const lines = [];
  let line = "";
  for (const tok of expandedTokens) {
    const candidate = line + tok;
    if (line !== "" && ctx.measureText(candidate).width > maxWidth) {
      lines.push(line);
      line = tok; // 새 줄 시작
      if (line.trim() === "" && line !== "") line = ""; // 줄 앞머리 공백 방지
    } else {
      line = candidate;
    }
  }
  if (line !== "") lines.push(line);
  return lines.length ? lines : [""];
}

function wrapText(ctx, text, maxWidth) {
  const paragraphs = text.split("\n");
  let allLines = [];
  for (const p of paragraphs) {
    allLines = allLines.concat(wrapParagraph(ctx, p, maxWidth));
  }
  return allLines;
}

function isLight(hex) {
  const c = (hex || "#000000").replace("#", "");
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  const luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luma > 0.6;
}

// ---------- 색상 값(단색 HEX 또는 그라데이션) ----------
// 문구/도형의 색은 두 가지 형태 중 하나: 문자열 "#rrggbb"(단색), 또는
// {type:"gradient", from:"#rrggbb", to:"#rrggbb", angle:0~360}(그라데이션).

function isValidColorValue(v) {
  if (typeof v === "string") return /^#[0-9a-fA-F]{6}$/.test(v);
  if (v && typeof v === "object" && v.type === "gradient") {
    return /^#[0-9a-fA-F]{6}$/.test(v.from || "") && /^#[0-9a-fA-F]{6}$/.test(v.to || "") && typeof v.angle === "number";
  }
  return false;
}

/** 밝은 색인지(테두리/대비 판단용). 그라데이션이면 두 색 중 더 밝은 쪽 기준으로 안전하게 판단한다. */
function isLightColorValue(v) {
  if (typeof v === "string") return isLight(v);
  if (v && v.type === "gradient") return isLight(v.from) || isLight(v.to);
  return false;
}

/** 색상 값을 실제 canvas fillStyle/strokeStyle로 바꾼다. 그라데이션이면 halfW/halfH 크기의
 *  상자에 걸쳐(각도 방향으로) 선형 그라데이션을 만든다. ctx는 이미 그릴 대상의 중심으로
 *  translate/rotate 되어 있어야 한다(0,0 기준 상대 좌표로 그라데이션 라인을 만들기 때문). */
function resolveFillStyle(ctx, colorValue, halfW, halfH) {
  if (colorValue && typeof colorValue === "object" && colorValue.type === "gradient") {
    const angle = ((colorValue.angle || 0) * Math.PI) / 180;
    const dx = Math.cos(angle) * Math.max(1, halfW);
    const dy = Math.sin(angle) * Math.max(1, halfH);
    const grad = ctx.createLinearGradient(-dx, -dy, dx, dy);
    grad.addColorStop(0, colorValue.from);
    grad.addColorStop(1, colorValue.to);
    return grad;
  }
  return colorValue || "#ffffff";
}

/** CSS 미리보기용(색상 스와치 배경). 그라데이션이면 CSS linear-gradient 문자열로. */
function cssPreviewForColorValue(v) {
  if (v && typeof v === "object" && v.type === "gradient") {
    return `linear-gradient(${v.angle || 0}deg, ${v.from}, ${v.to})`;
  }
  return v || "#ffffff";
}

function clampByte(n) {
  return Math.max(0, Math.min(255, Math.round(Number(n) || 0)));
}
function hexToRgb(hex) {
  const c = (hex || "#000000").replace("#", "");
  return { r: parseInt(c.substring(0, 2), 16) || 0, g: parseInt(c.substring(2, 4), 16) || 0, b: parseInt(c.substring(4, 6), 16) || 0 };
}
function rgbToHex(r, g, b) {
  const h = (n) => clampByte(n).toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

/**
 * 재사용 가능한 색상 컨트롤(단색 HEX/RGB + 그라데이션). container 안에 UI를 만들고 이벤트를 연결한다.
 * options.getValue(): 현재 색상 값(문자열 또는 그라데이션 객체)을 반환
 * options.setValue(v): 값이 바뀔 때마다 호출(호출부가 레이어에 반영 + renderAll)
 * options.onCommit(): "확정"된 변경(포커스 아웃/엔터/change)마다 호출(호출부가 recordHistory)
 * 반환값의 refresh()를 호출하면 getValue()의 현재 값으로 UI를 다시 채운다(레이어 전환 시 사용).
 */
function createColorControl(container, options) {
  container.innerHTML = `
    <button type="button" class="color-swatch"></button>
    <div class="color-panel" hidden>
      <div class="color-mode-tabs">
        <button type="button" data-mode="solid" class="mode-tab">단색</button>
        <button type="button" data-mode="gradient" class="mode-tab">그라데이션</button>
      </div>
      <div class="color-solid-fields">
        <div class="field-row">
          <label>HEX <input type="text" class="c-hex" placeholder="ffffff" maxlength="7" /></label>
        </div>
        <div class="rgb-row">
          <label>R<input type="number" class="c-r" min="0" max="255" /></label>
          <label>G<input type="number" class="c-g" min="0" max="255" /></label>
          <label>B<input type="number" class="c-b" min="0" max="255" /></label>
        </div>
      </div>
      <div class="color-gradient-fields" hidden>
        <div class="field-row"><label>시작 색 <input type="color" class="c-grad-from" /></label></div>
        <div class="field-row"><label>끝 색 <input type="color" class="c-grad-to" /></label></div>
        <div class="field-row"><label>각도 <span class="c-grad-angle-val"></span></label>
          <input type="range" class="c-grad-angle" min="0" max="360" value="90" /></div>
      </div>
    </div>
  `;
  const swatch = container.querySelector(".color-swatch");
  const panel = container.querySelector(".color-panel");
  const tabSolid = container.querySelector('[data-mode="solid"]');
  const tabGradient = container.querySelector('[data-mode="gradient"]');
  const solidFields = container.querySelector(".color-solid-fields");
  const gradientFields = container.querySelector(".color-gradient-fields");
  const hexEl = container.querySelector(".c-hex");
  const rEl = container.querySelector(".c-r");
  const gEl = container.querySelector(".c-g");
  const bEl = container.querySelector(".c-b");
  const gradFromEl = container.querySelector(".c-grad-from");
  const gradToEl = container.querySelector(".c-grad-to");
  const gradAngleEl = container.querySelector(".c-grad-angle");
  const gradAngleVal = container.querySelector(".c-grad-angle-val");

  function commit() {
    if (options.onCommit) options.onCommit();
  }

  function refresh() {
    const v = options.getValue();
    swatch.style.background = cssPreviewForColorValue(v);
    const isGradient = v && typeof v === "object" && v.type === "gradient";
    tabSolid.classList.toggle("active", !isGradient);
    tabGradient.classList.toggle("active", isGradient);
    solidFields.hidden = isGradient;
    gradientFields.hidden = !isGradient;
    if (isGradient) {
      gradFromEl.value = v.from;
      gradToEl.value = v.to;
      gradAngleEl.value = v.angle || 0;
      gradAngleVal.textContent = (v.angle || 0) + "°";
    } else {
      const hex = typeof v === "string" ? v : "#ffffff";
      hexEl.value = hex.replace("#", "");
      const rgb = hexToRgb(hex);
      rEl.value = rgb.r;
      gEl.value = rgb.g;
      bEl.value = rgb.b;
    }
  }

  swatch.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
  });

  tabSolid.addEventListener("click", () => {
    const v = options.getValue();
    const startFrom = v && typeof v === "object" ? v.from : v || "#ffffff";
    options.setValue(startFrom);
    refresh();
    commit();
  });
  tabGradient.addEventListener("click", () => {
    const v = options.getValue();
    const baseHex = typeof v === "string" ? v : "#ff4d6d";
    // 두 번째 색을 시작 색과 다르게 골라서, 전환하자마자 눈에 보이는 그라데이션이 되도록 한다.
    const toHex = baseHex.toLowerCase() === "#ffffff" ? "#ff4d6d" : "#ffffff";
    options.setValue({ type: "gradient", from: baseHex, to: toHex, angle: 90 });
    refresh();
    commit();
  });

  function applyHexInput(record) {
    const raw = hexEl.value.replace("#", "").trim();
    if (/^[0-9a-fA-F]{6}$/.test(raw)) {
      options.setValue("#" + raw.toLowerCase());
      const rgb = hexToRgb("#" + raw);
      rEl.value = rgb.r;
      gEl.value = rgb.g;
      bEl.value = rgb.b;
      swatch.style.background = "#" + raw;
      if (record) commit();
    }
  }
  hexEl.addEventListener("input", () => applyHexInput(false));
  hexEl.addEventListener("change", () => applyHexInput(true));

  function applyRgbInput(record) {
    const hex = rgbToHex(rEl.value, gEl.value, bEl.value);
    options.setValue(hex);
    hexEl.value = hex.replace("#", "");
    swatch.style.background = hex;
    if (record) commit();
  }
  [rEl, gEl, bEl].forEach((el) => {
    el.addEventListener("input", () => applyRgbInput(false));
    el.addEventListener("change", () => applyRgbInput(true));
  });

  function applyGradientInput(record) {
    options.setValue({ type: "gradient", from: gradFromEl.value, to: gradToEl.value, angle: Number(gradAngleEl.value) });
    gradAngleVal.textContent = gradAngleEl.value + "°";
    swatch.style.background = cssPreviewForColorValue(options.getValue());
    if (record) commit();
  }
  [gradFromEl, gradToEl, gradAngleEl].forEach((el) => {
    el.addEventListener("input", () => applyGradientInput(false));
    el.addEventListener("change", () => applyGradientInput(true));
  });

  refresh();
  return { refresh };
}

// ---------- 도형(벡터) 레이어: 하트 · 별 · 폭죽 ----------

function pathHeart(ctx, cx, cy, s) {
  const top = s * 0.3;
  ctx.beginPath();
  ctx.moveTo(cx, cy + top);
  ctx.bezierCurveTo(cx, cy, cx - s / 2, cy, cx - s / 2, cy + top);
  ctx.bezierCurveTo(cx - s / 2, cy + (s + top) / 2, cx, cy + (s + top) / 2, cx, cy + s);
  ctx.bezierCurveTo(cx, cy + (s + top) / 2, cx + s / 2, cy + (s + top) / 2, cx + s / 2, cy + top);
  ctx.bezierCurveTo(cx + s / 2, cy, cx, cy, cx, cy + top);
  ctx.closePath();
}

function pathStar(ctx, cx, cy, outerR, innerR, points) {
  points = points || 5;
  ctx.beginPath();
  const step = Math.PI / points;
  let rot = -Math.PI / 2;
  ctx.moveTo(cx + Math.cos(rot) * outerR, cy + Math.sin(rot) * outerR);
  for (let i = 0; i < points; i++) {
    rot += step;
    ctx.lineTo(cx + Math.cos(rot) * innerR, cy + Math.sin(rot) * innerR);
    rot += step;
    ctx.lineTo(cx + Math.cos(rot) * outerR, cy + Math.sin(rot) * outerR);
  }
  ctx.closePath();
}

/** 폭죽: 중심에서 사방으로 뻗는 획 + 끝점의 작은 점(단색/그라데이션 fillStyle을 그대로 사용). */
function drawFireworkBurst(ctx, size, fillStyle) {
  const rays = 10;
  ctx.strokeStyle = fillStyle;
  ctx.fillStyle = fillStyle;
  ctx.lineWidth = Math.max(1, size * 0.045);
  ctx.lineCap = "round";
  for (let i = 0; i < rays; i++) {
    const angle = (Math.PI * 2 * i) / rays;
    const len = size * (i % 2 === 0 ? 0.75 : 0.5);
    const x2 = Math.cos(angle) * len;
    const y2 = Math.sin(angle) * len;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(x2, y2, size * 0.05, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.beginPath();
  ctx.arc(0, 0, size * 0.09, 0, Math.PI * 2);
  ctx.fill();
}

function drawShapeLayer(ctx, w, h, layer) {
  const cx = w * (layer.x / 100);
  const cy = h * (layer.y / 100);
  const size = Math.max(4, (layer.size / 100) * h);

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(((layer.rotation || 0) * Math.PI) / 180);
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;

  const fillStyle = resolveFillStyle(ctx, layer.color, size, size);
  ctx.fillStyle = fillStyle;
  ctx.strokeStyle = fillStyle;

  if (layer.shapeKind === "star") {
    pathStar(ctx, 0, 0, size * 0.55, size * 0.22);
    ctx.fill();
  } else if (layer.shapeKind === "firework") {
    drawFireworkBurst(ctx, size, fillStyle);
  } else {
    pathHeart(ctx, 0, 0, size);
    ctx.fill();
  }

  ctx.restore();
}

// ---------- 합성 렌더링 (미리보기와 다운로드가 동일 함수 사용) ----------

function renderComposition(ctx, w, h, s, ratioKey) {
  ctx.clearRect(0, 0, w, h);

  if (s.image) {
    const img = s.image;
    const scale = Math.max(w / img.naturalWidth, h / img.naturalHeight);
    const dw = img.naturalWidth * scale;
    const dh = img.naturalHeight * scale;
    const dx = (w - dw) / 2;
    const dy = (h - dh) / 2;
    ctx.drawImage(img, dx, dy, dw, dh);
  } else {
    ctx.fillStyle = "#f0f0f3";
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#9a9aa5";
    ctx.font = `500 ${Math.round(h * 0.03)}px ${FONT_STACK}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText("이미지를 업로드하세요", w / 2, h / 2);
  }

  // 레이어를 순서대로(포토샵처럼 아래->위) 그린다. 문구/손글씨 레이어가 섞여 있으면
  // 배열에 있는 순서 그대로 겹쳐 그려진다.
  (s.layers || []).forEach((layer) => {
    if (layer.type === "ink") {
      drawInkLayer(ctx, layer, ratioKey);
    } else if (layer.type === "shape") {
      drawShapeLayer(ctx, w, h, layer);
    } else {
      drawTextLayer(ctx, w, h, layer);
    }
  });
}

function drawTextLayer(ctx, w, h, layer) {
  const text = (layer.text || "").trim() === "" ? "" : layer.text;
  if (text === "") return;

  const fontPx = Math.max(8, (layer.fontSize / 100) * h);
  ctx.font = fontDeclaration(layer.fontFamily, fontPx);
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const maxWidth = w * 0.86;
  const lines = wrapText(ctx, text, maxWidth);
  const lineHeight = fontPx * 1.25;
  const totalHeight = lines.length * lineHeight;
  const startYRel = -totalHeight / 2 + lineHeight / 2;
  const cx = w * (layer.x / 100);
  const cy = h * (layer.y / 100);

  const maxLineWidth = Math.max(1, ...lines.map((l) => ctx.measureText(l).width));

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(((layer.rotation || 0) * Math.PI) / 180);
  ctx.lineJoin = "round";

  const textFillStyle = resolveFillStyle(ctx, layer.color, maxLineWidth / 2, totalHeight / 2);

  // 네온: 같은 글자를 점점 흐리게(shadowBlur를 키워가며) 여러 번 겹쳐 그려 빛 번짐을 만든다.
  if (layer.neon && layer.neon.enabled) {
    [24, 14, 7].forEach((blur) => {
      ctx.shadowColor = layer.neon.color;
      ctx.shadowBlur = blur;
      ctx.shadowOffsetX = 0;
      ctx.shadowOffsetY = 0;
      ctx.fillStyle = layer.neon.color;
      lines.forEach((line, i) => ctx.fillText(line, 0, startYRel + i * lineHeight));
    });
  }

  lines.forEach((line, i) => {
    const ly = startYRel + i * lineHeight;
    ctx.shadowColor = "transparent";
    ctx.shadowBlur = 0;
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = 0;
    if (layer.stroke) {
      ctx.strokeStyle = isLightColorValue(layer.color) ? "#000000" : "#ffffff";
      ctx.lineWidth = Math.max(2, fontPx * 0.09);
      ctx.strokeText(line, 0, ly);
    }
    if (layer.shadow && layer.shadow.enabled) {
      ctx.shadowColor = layer.shadow.color;
      ctx.shadowBlur = layer.shadow.blur;
      ctx.shadowOffsetX = Math.max(2, fontPx * 0.05);
      ctx.shadowOffsetY = Math.max(2, fontPx * 0.05);
    }
    ctx.fillStyle = textFillStyle;
    ctx.fillText(line, 0, ly);
  });

  ctx.restore();
}

/** 손글씨/그림(필기) 레이어 한 개를 그린다. 애플펜슬·와콤펜 등에서 오는
 *  압력값(pressure)에 따라 선 굵기를 달리해서 필기감을 살린다. */
function drawInkLayer(ctx, layer, ratioKey) {
  const strokes = (layer.strokes && layer.strokes[ratioKey]) || [];
  ctx.shadowColor = "transparent";
  ctx.shadowBlur = 0;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  strokes.forEach((stroke) => {
    const points = (stroke && stroke.points) || [];
    if (points.length === 0) return;
    const color = stroke.color || layer.penColor;
    const width = stroke.width || layer.penWidth;
    if (points.length === 1) {
      const p = points[0];
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, (width * (p.pressure || 0.5)) / 2, 0, Math.PI * 2);
      ctx.fill();
      return;
    }
    for (let i = 1; i < points.length; i++) {
      const p0 = points[i - 1];
      const p1 = points[i];
      const pressure = ((p0.pressure || 0.5) + (p1.pressure || 0.5)) / 2;
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, width * pressure);
      ctx.beginPath();
      ctx.moveTo(p0.x, p0.y);
      ctx.lineTo(p1.x, p1.y);
      ctx.stroke();
    }
  });
}

// ---------- 미리보기 캔버스 3개 생성 ----------

const canvases = {}; // key -> canvas

function buildPreviewGrid() {
  const grid = $("previewGrid");
  grid.innerHTML = "";
  RATIOS.forEach((r) => {
    const item = document.createElement("div");
    item.className = "preview-item";

    const title = document.createElement("h3");
    title.textContent = `${r.label} (${r.w}×${r.h}px 결과 파일)`;

    const canvas = document.createElement("canvas");
    canvas.width = r.w;
    canvas.height = r.h;
    canvas.id = `canvas-${r.key.replace(":", "x")}`;

    const btn = document.createElement("button");
    btn.className = "dl-btn";
    btn.textContent = `${r.label} PNG 다운로드`;
    btn.addEventListener("click", () => downloadCanvas(canvas, r.key));

    item.appendChild(title);
    item.appendChild(canvas);
    item.appendChild(btn);
    grid.appendChild(item);

    canvases[r.key] = canvas;
    attachInkHandlers(canvas, r.key);
  });
}

// ---------- 손글씨/그림(필기) 입력 ----------
// Pointer Events(https://developer.mozilla.org/docs/Web/API/Pointer_events)를 사용하므로
// 마우스는 물론 터치, 애플펜슬(iPadOS Safari), 와콤 등 펜 태블릿이 보내는 pressure(압력)까지
// 별도 SDK 없이 표준 브라우저 API로 그대로 받아 선 굵기에 반영한다.

let activeStroke = null; // 현재 그리고 있는 획: { layerId, ratioKey, stroke }
let lastInkRatio = null; // 마지막으로 필기한 비율(되돌리기 대상 판단용)
let lastInkLayerId = null; // 마지막으로 필기한 레이어

/** 지금 선택된(active) 레이어가 손글씨 레이어일 때만 그릴 수 있다.
 *  "필기 모드" 체크박스 대신, 손글씨 레이어를 고르는 것 자체가 곧 "그리기 모드"다. */
function canvasPoint(canvas, evt) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: (evt.clientX - rect.left) * scaleX,
    y: (evt.clientY - rect.top) * scaleY,
    pressure: evt.pressure && evt.pressure > 0 ? evt.pressure : 0.5,
  };
}

function attachInkHandlers(canvas, ratioKey) {
  canvas.addEventListener("pointerdown", (e) => {
    const layer = getActiveLayer();
    if (!layer || layer.type !== "ink") return;
    e.preventDefault();
    try {
      canvas.setPointerCapture(e.pointerId);
    } catch (err) {
      /* 합성 이벤트 등 캡처가 불가능한 환경에서도 그리기 자체는 계속 진행한다 */
    }
    const pt = canvasPoint(canvas, e);
    const stroke = { color: layer.penColor, width: layer.penWidth, points: [pt] };
    activeStroke = { layerId: layer.id, ratioKey, stroke };
    layer.strokes[ratioKey].push(stroke);
    scheduleRenderAll();
  });

  canvas.addEventListener("pointermove", (e) => {
    if (!activeStroke || activeStroke.ratioKey !== ratioKey || activeStroke.layerId !== state.activeLayerId) return;
    e.preventDefault();
    activeStroke.stroke.points.push(canvasPoint(canvas, e));
    scheduleRenderAll();
  });

  const finish = (e) => {
    if (!activeStroke || activeStroke.ratioKey !== ratioKey) return;
    try {
      canvas.releasePointerCapture(e.pointerId);
    } catch (err) {
      /* 이미 해제된 경우 무시 */
    }
    lastInkRatio = ratioKey;
    lastInkLayerId = activeStroke.layerId;
    activeStroke = null;
    renderAll();
    recordHistory(`손글씨 추가 (${ratioKey})`);
  };
  canvas.addEventListener("pointerup", finish);
  canvas.addEventListener("pointercancel", finish);
}

/** 지금 선택된 레이어가 손글씨 레이어인지에 따라 캔버스 커서를 바꿔 보여준다. */
function updateCanvasCursor() {
  const layer = getActiveLayer();
  const isInk = !!layer && layer.type === "ink";
  Object.values(canvases).forEach((c) => c.classList.toggle("ink-cursor", isInk));
}

function undoLastInkStroke() {
  const layer = getActiveLayer();
  if (!layer || layer.type !== "ink") return;
  const ratioKey = lastInkLayerId === layer.id && lastInkRatio ? lastInkRatio : RATIOS[0].key;
  const arr = layer.strokes[ratioKey];
  if (!arr || arr.length === 0) return;
  arr.pop();
  renderAll();
  recordHistory(`손글씨 실행취소 (${ratioKey})`);
}

function clearActiveInkLayer() {
  const layer = getActiveLayer();
  if (!layer || layer.type !== "ink") return;
  RATIOS.forEach((r) => {
    layer.strokes[r.key] = [];
  });
  renderAll();
  recordHistory("손글씨 레이어 지우기");
}

// ---------- 손글씨 인식(OCR) -> 문구 레이어로 변환 ----------
// Tesseract.js(https://github.com/naptha/tesseract.js)를 CDN에서 불러와 브라우저 안에서만 인식한다
// (서버로 이미지를 보내지 않음). 인쇄체/스캔 문서용으로 훈련된 엔진이라 자유롭게 휘갈겨 쓴 손글씨는
// 인식률이 낮을 수 있으니, 결과는 항상 사용자가 확인·수정하는 것을 전제로 한다.
// 인식 언어는 "인식 언어" 드롭다운(#inkRecognizeLang)에서 고른 값을 그대로 Tesseract.recognize()에
// 넘긴다 — 한국어+영어(기본), 한국어만, 영어만, 일본어, 중국어(간체/번체) 중 선택 가능.

function showInkRecognizeStatus(msg, isError) {
  const el = $("inkRecognizeStatus");
  el.textContent = msg;
  el.className = isError ? "error" : "hint";
  el.hidden = false;
}

/** 손글씨 레이어 한 개(특정 비율)를 흰 배경 위에 그려서 OCR에 넣기 좋은 이미지로 만든다. */
function renderInkLayerToWhiteCanvas(layer, ratioKey) {
  const r = RATIOS.find((x) => x.key === ratioKey);
  const c = document.createElement("canvas");
  c.width = r.w;
  c.height = r.h;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, r.w, r.h);
  drawInkLayer(ctx, layer, ratioKey);
  return c.toDataURL("image/png");
}

async function onRecognizeInkLayer() {
  const layer = getActiveLayer();
  if (!layer || layer.type !== "ink") return;

  const ratioKey = RATIOS.map((r) => r.key).find((k) => (layer.strokes[k] || []).length > 0);
  if (!ratioKey) {
    showInkRecognizeStatus("인식할 손글씨가 없습니다. 먼저 캔버스 위에 그려주세요.", true);
    return;
  }

  if (typeof Tesseract === "undefined") {
    showInkRecognizeStatus(
      "손글씨 인식 엔진을 불러오지 못했습니다(인터넷 연결을 확인해주세요). 잠시 후 다시 시도하거나 직접 타이핑해주세요.",
      true
    );
    return;
  }

  const lang = $("inkRecognizeLang").value || "kor+eng";
  $("inkRecognizeBtn").disabled = true;
  showInkRecognizeStatus("인식 중입니다... (해당 언어를 처음 쓴다면 인식 데이터를 내려받느라 시간이 걸릴 수 있어요)", false);

  try {
    const dataUrl = renderInkLayerToWhiteCanvas(layer, ratioKey);
    const result = await Tesseract.recognize(dataUrl, lang);
    const text = ((result && result.data && result.data.text) || "").trim();
    $("inkRecognizeBtn").disabled = false;

    if (!text) {
      showInkRecognizeStatus("글자를 인식하지 못했습니다. 더 또박또박 써보거나 직접 타이핑해주세요.", true);
      return;
    }

    showInkRecognizeStatus(`인식됨: "${truncateLabel(text, 30)}" → 새 문구 레이어에 담았습니다. 결과를 확인하고 고쳐주세요.`, false);

    const newLayer = makeLayer({ type: "text", text });
    const idx = state.layers.findIndex((l) => l.id === layer.id);
    state.layers.splice(idx + 1, 0, newLayer);
    state.activeLayerId = newLayer.id;
    syncControlsFromActiveLayer();
    renderLayerChips();
    renderAll();
    recordHistory(`손글씨 인식 → 문구 레이어 생성: "${truncateLabel(text, 24)}"`);
  } catch (err) {
    $("inkRecognizeBtn").disabled = false;
    showInkRecognizeStatus(
      "손글씨 인식에 실패했습니다(네트워크 문제일 수 있어요). 잠시 후 다시 시도하거나 직접 타이핑해주세요.",
      true
    );
  }
}

let renderScheduled = false;
function renderAll() {
  RATIOS.forEach((r) => {
    const canvas = canvases[r.key];
    const ctx = canvas.getContext("2d");
    renderComposition(ctx, r.w, r.h, state, r.key);
  });
}

/** pointermove처럼 아주 자주 발생하는 이벤트에서 중복 렌더를 줄이기 위한 rAF 코얼레싱. */
function scheduleRenderAll() {
  if (renderScheduled) return;
  renderScheduled = true;
  requestAnimationFrame(() => {
    renderScheduled = false;
    renderAll();
  });
}

function downloadCanvas(canvas, ratioKey) {
  canvas.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `quiplet-${ratioKey.replace(":", "-")}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }, "image/png");
}

// ---------- 문구 레이어 UI ----------

const SHAPE_KIND_LABEL = { heart: "하트", star: "별", firework: "폭죽" };

function layerLabel(layer, index) {
  if (layer.type === "ink") {
    const total = RATIOS.reduce((sum, r) => sum + (((layer.strokes || {})[r.key] || []).length), 0);
    return `${index + 1}. ✍️ 손글씨${total ? ` (${total}획)` : ""}`;
  }
  if (layer.type === "shape") {
    return `${index + 1}. ✨ ${SHAPE_KIND_LABEL[layer.shapeKind] || "도형"}`;
  }
  const t = truncateLabel(layer.text, 10);
  return t ? `${index + 1}. ${t}` : `${index + 1}. (빈 문구)`;
}

function renderLayerChips() {
  const wrap = $("layerChips");
  wrap.innerHTML = "";
  state.layers.forEach((layer, i) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "layer-chip" + (layer.id === state.activeLayerId ? " active" : "");
    chip.textContent = layerLabel(layer, i);
    chip.addEventListener("click", () => {
      state.activeLayerId = layer.id;
      syncControlsFromActiveLayer();
      renderLayerChips();
    });
    wrap.appendChild(chip);
  });
  $("delLayerBtn").disabled = state.layers.length <= 1;
}

/** 좌측 컨트롤들을 지금 선택된(active) 레이어의 종류·값에 맞춰 채운다.
 *  레이어 종류(문구/손글씨/도형)에 따라 보여줄 컨트롤 블록 자체가 달라진다. */
function syncControlsFromActiveLayer() {
  const layer = getActiveLayer();
  const isInk = layer.type === "ink";
  const isShape = layer.type === "shape";
  const isText = !isInk && !isShape;

  $("textLayerControls").hidden = !isText;
  $("inkLayerControls").hidden = !isInk;
  $("shapeLayerControls").hidden = !isShape;
  $("featureMenuBtn").hidden = !isText;
  $("inkRecognizeStatus").hidden = true; // 레이어를 바꾸면 이전 인식 결과 메시지는 지운다

  // 위치(가로/세로) 슬라이더는 미리보기 바로 아래 "위치" 패널에 따로 모아, 화면을 보면서 조절하게 한다.
  $("positionControlsText").hidden = !isText;
  $("positionControlsShape").hidden = !isShape;
  $("positionPanelNone").hidden = !isInk;
  $("positionPanelLayerName").textContent = layerLabel(layer, state.layers.indexOf(layer));
  if (!isText) {
    $("featureMenu").hidden = true;
    $("rotationBlock").hidden = true;
    $("shadowBlock").hidden = true;
    $("neonBlock").hidden = true;
  }

  if (isText) {
    $("textInput").value = layer.text;
    $("posX").value = layer.x;
    $("posY").value = layer.y;
    $("fontSize").value = layer.fontSize;
    $("fontFamily").value = FONT_OPTIONS[layer.fontFamily] ? layer.fontFamily : "default";
    $("strokeToggle").checked = layer.stroke;
    $("posXVal").textContent = layer.x + "%";
    $("posYVal").textContent = layer.y + "%";
    $("fontSizeVal").textContent = layer.fontSize + "%";
    if (textColorControl) textColorControl.refresh();

    $("rotation").value = layer.rotation || 0;
    $("rotationVal").textContent = (layer.rotation || 0) + "°";

    const shadow = layer.shadow || { enabled: false, color: "#000000", blur: 10 };
    $("featShadow").checked = !!shadow.enabled;
    $("shadowBlock").hidden = !shadow.enabled;
    $("shadowColor").value = shadow.color;
    $("shadowBlur").value = shadow.blur;
    $("shadowBlurVal").textContent = shadow.blur + "px";

    const neon = layer.neon || { enabled: false, color: "#00eaff" };
    $("featNeon").checked = !!neon.enabled;
    $("neonBlock").hidden = !neon.enabled;
    $("neonColor").value = neon.color;
  } else if (isInk) {
    $("inkColor").value = layer.penColor;
    $("inkWidth").value = layer.penWidth;
    $("inkWidthVal").textContent = layer.penWidth + "px";
  } else if (isShape) {
    $("shapeKind").value = layer.shapeKind;
    $("shapeX").value = layer.x;
    $("shapeY").value = layer.y;
    $("shapeSize").value = layer.size;
    $("shapeRotation").value = layer.rotation || 0;
    $("shapeXVal").textContent = layer.x + "%";
    $("shapeYVal").textContent = layer.y + "%";
    $("shapeSizeVal").textContent = layer.size + "%";
    $("shapeRotationVal").textContent = (layer.rotation || 0) + "°";
    if (shapeColorControl) shapeColorControl.refresh();
  }

  updateCanvasCursor();
}

function onDuplicateLayer() {
  const src = getActiveLayer();
  const copy = deepClone(src, makeLayer({ type: src.type }));
  copy.id = uid();
  if (copy.type !== "ink" && typeof copy.y === "number") {
    copy.y = Math.max(5, Math.min(95, src.y - 12)); // 겹치지 않도록 살짝 위로 옮겨서 바로 눈에 띄게
  }
  const idx = state.layers.findIndex((l) => l.id === src.id);
  state.layers.splice(idx + 1, 0, copy);
  state.activeLayerId = copy.id;
  syncControlsFromActiveLayer();
  renderLayerChips();
  renderAll();
  recordHistory(`레이어 복사 (${layerLabel(copy, idx + 1)})`);
}

function onAddInkLayer() {
  const src = getActiveLayer();
  const newLayer = makeLayer({ type: "ink" });
  const idx = state.layers.findIndex((l) => l.id === src.id);
  const insertAt = idx === -1 ? state.layers.length : idx + 1;
  state.layers.splice(insertAt, 0, newLayer);
  state.activeLayerId = newLayer.id;
  syncControlsFromActiveLayer();
  renderLayerChips();
  renderAll();
  recordHistory("손글씨 레이어 추가");
}

function onAddShapeLayer() {
  const src = getActiveLayer();
  const newLayer = makeLayer({ type: "shape" });
  const idx = state.layers.findIndex((l) => l.id === src.id);
  const insertAt = idx === -1 ? state.layers.length : idx + 1;
  state.layers.splice(insertAt, 0, newLayer);
  state.activeLayerId = newLayer.id;
  syncControlsFromActiveLayer();
  renderLayerChips();
  renderAll();
  recordHistory(`도형 레이어 추가 (${SHAPE_KIND_LABEL[newLayer.shapeKind]})`);
}

function onDeleteLayer() {
  if (state.layers.length <= 1) return;
  const idx = state.layers.findIndex((l) => l.id === state.activeLayerId);
  if (idx === -1) return;
  const removed = state.layers.splice(idx, 1)[0];
  state.activeLayerId = state.layers[Math.max(0, idx - 1)].id;
  syncControlsFromActiveLayer();
  renderLayerChips();
  renderAll();
  const label =
    removed.type === "ink"
      ? "손글씨 레이어"
      : removed.type === "shape"
      ? `${SHAPE_KIND_LABEL[removed.shapeKind] || "도형"} 레이어`
      : truncateLabel(removed.text, 16) || "(빈 문구)";
  recordHistory(`레이어 삭제 (${label})`);
}

// ---------- 컨트롤 바인딩 ----------

function bindControls() {
  const dropzone = $("dropzone");
  const fileInput = $("fileInput");

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });
  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) handleFile(e.target.files[0]);
    fileInput.value = "";
  });
  ["dragenter", "dragover"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    })
  );
  dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  $("dupLayerBtn").addEventListener("click", onDuplicateLayer);
  $("addInkLayerBtn").addEventListener("click", onAddInkLayer);
  $("addShapeLayerBtn").addEventListener("click", onAddShapeLayer);
  $("delLayerBtn").addEventListener("click", onDeleteLayer);

  textColorControl = createColorControl($("textColorControl"), {
    getValue: () => getActiveLayer().color,
    setValue: (v) => {
      getActiveLayer().color = v;
      renderAll();
    },
    onCommit: () => recordHistory("글자 색 변경"),
  });
  shapeColorControl = createColorControl($("shapeColorControl"), {
    getValue: () => getActiveLayer().color,
    setValue: (v) => {
      getActiveLayer().color = v;
      renderAll();
    },
    onCommit: () => recordHistory("도형 색 변경"),
  });

  const recordTextChange = debounce(() => {
    const t = getActiveLayer().text;
    recordHistory(`문구 변경: "${truncateLabel(t, 24) || "(빈 문구)"}"`);
  }, 800);
  $("textInput").addEventListener("input", (e) => {
    const layer = getActiveLayer();
    layer.text = e.target.value;
    renderLayerChips();
    $("positionPanelLayerName").textContent = layerLabel(layer, state.layers.indexOf(layer));
    renderAll();
    recordTextChange();
  });

  $("posX").addEventListener("input", (e) => {
    getActiveLayer().x = Number(e.target.value);
    $("posXVal").textContent = e.target.value + "%";
    renderAll();
  });
  $("posX").addEventListener("change", () => {
    recordHistory(`가로 위치 변경: ${getActiveLayer().x}%`);
  });
  $("posY").addEventListener("input", (e) => {
    getActiveLayer().y = Number(e.target.value);
    $("posYVal").textContent = e.target.value + "%";
    renderAll();
  });
  $("posY").addEventListener("change", () => {
    recordHistory(`세로 위치 변경: ${getActiveLayer().y}%`);
  });
  $("fontSize").addEventListener("input", (e) => {
    getActiveLayer().fontSize = Number(e.target.value);
    $("fontSizeVal").textContent = e.target.value + "%";
    renderAll();
  });
  $("fontSize").addEventListener("change", () => {
    recordHistory(`글자 크기 변경: ${getActiveLayer().fontSize}%`);
  });
  $("strokeToggle").addEventListener("change", (e) => {
    const layer = getActiveLayer();
    layer.stroke = e.target.checked;
    renderAll();
    recordHistory(`테두리 옵션: ${layer.stroke ? "켜짐" : "꺼짐"}`);
  });
  $("fontFamily").addEventListener("change", (e) => {
    getActiveLayer().fontFamily = e.target.value;
    renderAll();
    recordHistory(`글꼴 변경: ${e.target.options[e.target.selectedIndex].text}`);
  });

  // + 기능 추가 메뉴(펼침/접힘으로 화면을 덜 복잡하게 유지)
  $("featureMenuBtn").addEventListener("click", () => {
    $("featureMenu").hidden = !$("featureMenu").hidden;
  });
  $("featRotation").addEventListener("change", (e) => {
    $("rotationBlock").hidden = !e.target.checked;
  });
  $("featShadow").addEventListener("change", (e) => {
    const layer = getActiveLayer();
    layer.shadow.enabled = e.target.checked;
    $("shadowBlock").hidden = !e.target.checked;
    renderAll();
    recordHistory(`그림자 ${e.target.checked ? "켜짐" : "꺼짐"}`);
  });
  $("featNeon").addEventListener("change", (e) => {
    const layer = getActiveLayer();
    layer.neon.enabled = e.target.checked;
    $("neonBlock").hidden = !e.target.checked;
    renderAll();
    recordHistory(`네온 글씨 ${e.target.checked ? "켜짐" : "꺼짐"}`);
  });
  $("rotation").addEventListener("input", (e) => {
    getActiveLayer().rotation = Number(e.target.value);
    $("rotationVal").textContent = e.target.value + "°";
    renderAll();
  });
  $("rotation").addEventListener("change", () => {
    recordHistory(`회전 변경: ${getActiveLayer().rotation}°`);
  });

  $("shadowColor").addEventListener("input", (e) => {
    getActiveLayer().shadow.color = e.target.value;
    renderAll();
  });
  $("shadowColor").addEventListener("change", () => {
    recordHistory(`그림자 색 변경: ${getActiveLayer().shadow.color}`);
  });
  $("shadowBlur").addEventListener("input", (e) => {
    getActiveLayer().shadow.blur = Number(e.target.value);
    $("shadowBlurVal").textContent = e.target.value + "px";
    renderAll();
  });
  $("shadowBlur").addEventListener("change", () => {
    recordHistory(`그림자 번짐 변경: ${getActiveLayer().shadow.blur}px`);
  });

  $("neonColor").addEventListener("input", (e) => {
    getActiveLayer().neon.color = e.target.value;
    renderAll();
  });
  $("neonColor").addEventListener("change", () => {
    recordHistory(`네온 색 변경: ${getActiveLayer().neon.color}`);
  });

  $("inkColor").addEventListener("input", (e) => {
    const layer = getActiveLayer();
    if (layer.type === "ink") layer.penColor = e.target.value;
    renderAll();
  });
  $("inkColor").addEventListener("change", () => {
    const layer = getActiveLayer();
    if (layer.type === "ink") recordHistory(`펜 색 변경: ${layer.penColor}`);
  });
  $("inkWidth").addEventListener("input", (e) => {
    const layer = getActiveLayer();
    if (layer.type === "ink") layer.penWidth = Number(e.target.value);
    $("inkWidthVal").textContent = e.target.value + "px";
  });
  $("inkWidth").addEventListener("change", () => {
    const layer = getActiveLayer();
    if (layer.type === "ink") recordHistory(`펜 굵기 변경: ${layer.penWidth}px`);
  });
  $("inkUndoBtn").addEventListener("click", undoLastInkStroke);
  $("inkClearBtn").addEventListener("click", clearActiveInkLayer);
  $("inkRecognizeBtn").addEventListener("click", onRecognizeInkLayer);

  $("shapeKind").addEventListener("change", (e) => {
    getActiveLayer().shapeKind = e.target.value;
    renderLayerChips();
    renderAll();
    recordHistory(`도형 모양 변경: ${SHAPE_KIND_LABEL[e.target.value]}`);
  });
  $("shapeX").addEventListener("input", (e) => {
    getActiveLayer().x = Number(e.target.value);
    $("shapeXVal").textContent = e.target.value + "%";
    renderAll();
  });
  $("shapeX").addEventListener("change", () => {
    recordHistory(`도형 가로 위치 변경: ${getActiveLayer().x}%`);
  });
  $("shapeY").addEventListener("input", (e) => {
    getActiveLayer().y = Number(e.target.value);
    $("shapeYVal").textContent = e.target.value + "%";
    renderAll();
  });
  $("shapeY").addEventListener("change", () => {
    recordHistory(`도형 세로 위치 변경: ${getActiveLayer().y}%`);
  });
  $("shapeSize").addEventListener("input", (e) => {
    getActiveLayer().size = Number(e.target.value);
    $("shapeSizeVal").textContent = e.target.value + "%";
    renderAll();
  });
  $("shapeSize").addEventListener("change", () => {
    recordHistory(`도형 크기 변경: ${getActiveLayer().size}%`);
  });
  $("shapeRotation").addEventListener("input", (e) => {
    getActiveLayer().rotation = Number(e.target.value);
    $("shapeRotationVal").textContent = e.target.value + "°";
    renderAll();
  });
  $("shapeRotation").addEventListener("change", () => {
    recordHistory(`도형 회전 변경: ${getActiveLayer().rotation}°`);
  });

  $("addHistoryBtn").addEventListener("click", () => {
    recordHistory("수동 체크포인트");
  });

  $("saveTemplateBtn").addEventListener("click", onSaveNewTemplate);
  $("updateTemplateBtn").addEventListener("click", onUpdateTemplate);
  $("exportJsonBtn").addEventListener("click", onExportJson);
  $("importJsonInput").addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) onImportJson(e.target.files[0]);
    e.target.value = "";
  });
}

// ---------- 템플릿 CRUD ----------

function stateToTemplate(name, id) {
  return {
    id: id || uid(),
    name,
    layers: cloneLayers(state.layers), // 문구 레이어와 손글씨 레이어가 함께 담긴다
    image: state.image ? canvasImageToDataURL(state.image) : null,
    imageName: state.imageName || null,
    updatedAt: new Date().toISOString(),
  };
}

function canvasImageToDataURL(img) {
  // 원본 이미지를 그대로 dataURL로 저장(위치정보 등 EXIF 없는 순수 픽셀만 보존)
  const c = document.createElement("canvas");
  c.width = img.naturalWidth;
  c.height = img.naturalHeight;
  const ctx = c.getContext("2d");
  ctx.drawImage(img, 0, 0);
  return c.toDataURL("image/png");
}

function onSaveNewTemplate() {
  const name = window.prompt("템플릿 이름을 입력하세요", `템플릿 ${templates.length + 1}`);
  if (name === null) return;
  const t = stateToTemplate(name.trim() || `템플릿 ${templates.length + 1}`);
  templates.push(t);
  saveTemplatesToStorage();
  currentTemplateId = t.id;
  $("updateTemplateBtn").disabled = false;
  renderTemplateList();
}

function onUpdateTemplate() {
  if (!currentTemplateId) return;
  const idx = templates.findIndex((t) => t.id === currentTemplateId);
  if (idx === -1) return;
  templates[idx] = stateToTemplate(templates[idx].name, currentTemplateId);
  saveTemplatesToStorage();
  renderTemplateList();
}

/** 예전(레이어·글꼴·필기 기능이 없던 시절) 템플릿의 평평한 필드를 레이어 1개로 감싼다. */
function layersFromLegacyFields(t) {
  return [
    makeLayer({
      text: t.text || "",
      x: t.x,
      y: t.y,
      fontSize: t.fontSize,
      color: t.color,
      fontFamily: t.fontFamily && FONT_OPTIONS[t.fontFamily] ? t.fontFamily : "default",
      stroke: t.stroke !== false,
    }),
  ];
}

/** 아주 예전 형식(레이어 안이 아니라 최상위에 전역 손글씨 데이터가 있던 시절)을
 *  현재의 "손글씨 레이어" 하나로 옮겨준다. 없으면 아무 것도 추가하지 않는다. */
function legacyInkAsLayer(legacyInk) {
  if (!legacyInk || typeof legacyInk !== "object" || Array.isArray(legacyInk)) return null;
  const hasAnyStroke = RATIOS.some((r) => Array.isArray(legacyInk[r.key]) && legacyInk[r.key].length > 0);
  if (!hasAnyStroke) return null;
  return makeLayer({
    type: "ink",
    strokes: {
      "1:1": deepClone(legacyInk["1:1"] || [], []),
      "4:5": deepClone(legacyInk["4:5"] || [], []),
      "9:16": deepClone(legacyInk["9:16"] || [], []),
    },
  });
}

/** 템플릿/가져온 JSON 항목을 지금 레이어 배열 형태로 정규화한다(예전 형식 호환 포함). */
function normalizeLoadedLayers(t) {
  let layers = Array.isArray(t.layers) && t.layers.length ? cloneLayers(t.layers) : layersFromLegacyFields(t);
  // 각 레이어에 종류/회전/그림자/네온 기본값이 빠져 있을 수 있으니(예전 템플릿) 보정한다.
  layers = layers.map((l) => makeLayer(l));
  const migratedInk = legacyInkAsLayer(t.ink);
  if (migratedInk) layers = layers.concat([migratedInk]);
  return layers;
}

function loadTemplateIntoEditor(t) {
  state.layers = normalizeLoadedLayers(t);
  state.activeLayerId = state.layers[0].id;
  currentTemplateId = t.id;

  syncControlsFromActiveLayer();
  renderLayerChips();
  $("updateTemplateBtn").disabled = false;

  if (t.image) {
    const img = new Image();
    img.onload = () => {
      state.image = img;
      state.imageName = t.imageName || "template-image";
      $("fileInfo").textContent = `템플릿 이미지 불러옴: ${state.imageName}`;
      renderAll();
      recordHistory(`템플릿 불러옴: ${t.name}`);
    };
    img.src = t.image;
  } else {
    state.image = null;
    renderAll();
    recordHistory(`템플릿 불러옴: ${t.name}`);
  }
}

function deleteTemplate(id) {
  templates = templates.filter((t) => t.id !== id);
  saveTemplatesToStorage();
  if (currentTemplateId === id) {
    currentTemplateId = null;
    $("updateTemplateBtn").disabled = true;
  }
  renderTemplateList();
}

function renderTemplateList() {
  const list = $("templateList");
  const empty = $("templateEmpty");
  list.innerHTML = "";
  if (templates.length === 0) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  templates.forEach((t) => {
    const li = document.createElement("li");
    li.className = "template-item";

    const name = document.createElement("div");
    name.className = "t-name";
    name.textContent = t.name;

    const meta = document.createElement("div");
    meta.className = "t-meta";
    meta.textContent = t.updatedAt ? new Date(t.updatedAt).toLocaleString() : "";

    const actions = document.createElement("div");
    actions.className = "t-actions";

    const loadBtn = document.createElement("button");
    loadBtn.textContent = "불러오기";
    loadBtn.addEventListener("click", () => loadTemplateIntoEditor(t));

    const delBtn = document.createElement("button");
    delBtn.textContent = "삭제";
    delBtn.className = "danger";
    delBtn.addEventListener("click", () => deleteTemplate(t.id));

    actions.appendChild(loadBtn);
    actions.appendChild(delBtn);

    li.appendChild(name);
    li.appendChild(meta);
    li.appendChild(actions);
    list.appendChild(li);
  });
}

// ---------- 편집 기록(히스토리) ----------
// 포토샵 히스토리 패널과 비슷하게: 편집할 때마다 순서대로 기록이 남고,
// 예전 기록을 클릭하면 그 시점 상태로 되돌아가 이어서 편집할 수 있다.
// 되돌아간 뒤 새로 편집하면(=새 기록 추가) 그 이후의 미래 기록은 잘려나간다.

function snapshotState(label) {
  return {
    id: uid(),
    label,
    time: new Date().toISOString(),
    snapshot: {
      layers: cloneLayers(state.layers),
      activeLayerId: state.activeLayerId,
      image: state.image ? canvasImageToDataURL(state.image) : null,
      imageName: state.imageName || null,
    },
  };
}

function recordHistory(label) {
  // 예전 기록으로 돌아간 상태에서 새로 편집하면 그 이후 기록은 버린다(분기 방지).
  if (historyIndex < history.length - 1) {
    history = history.slice(0, historyIndex + 1);
  }
  history.push(snapshotState(label));
  if (history.length > HISTORY_LIMIT) {
    history = history.slice(history.length - HISTORY_LIMIT);
  }
  historyIndex = history.length - 1;
  renderHistoryList();
}

function restoreHistory(index) {
  const entry = history[index];
  if (!entry) return;
  const s = entry.snapshot;
  state.layers = cloneLayers(s.layers && s.layers.length ? s.layers : [makeLayer({ type: "text" })]).map((l) => makeLayer(l));
  state.activeLayerId = s.activeLayerId && state.layers.some((l) => l.id === s.activeLayerId) ? s.activeLayerId : state.layers[0].id;

  syncControlsFromActiveLayer();
  renderLayerChips();

  historyIndex = index;
  renderHistoryList();

  if (s.image) {
    const img = new Image();
    img.onload = () => {
      state.image = img;
      state.imageName = s.imageName || "history-image";
      $("fileInfo").textContent = `기록에서 불러옴: ${state.imageName}`;
      renderAll();
    };
    img.src = s.image;
  } else {
    state.image = null;
    renderAll();
  }
}

function truncateLabel(text, max) {
  const t = (text || "").replace(/\n/g, " ");
  return t.length > max ? t.slice(0, max) + "…" : t;
}

function renderHistoryList() {
  const list = $("historyList");
  const empty = $("historyEmpty");
  list.innerHTML = "";
  if (history.length === 0) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  history.forEach((entry, i) => {
    const li = document.createElement("li");
    li.className = "history-item" + (i === historyIndex ? " current" : "");

    const idx = document.createElement("span");
    idx.className = "h-index";
    idx.textContent = i + 1 + ".";

    const body = document.createElement("div");
    body.className = "h-body";
    const label = document.createElement("div");
    label.className = "h-label";
    label.textContent = entry.label;
    const time = document.createElement("div");
    time.className = "h-time";
    time.textContent = new Date(entry.time).toLocaleTimeString();
    body.appendChild(label);
    body.appendChild(time);

    li.appendChild(idx);
    li.appendChild(body);
    li.addEventListener("click", () => restoreHistory(i));
    list.appendChild(li);
  });
}

// ---------- JSON 내보내기 / 가져오기(복원) ----------

function onExportJson() {
  const blob = new Blob([JSON.stringify(templates, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "quiplet-templates.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function showJsonError(msg) {
  const el = $("jsonError");
  el.textContent = msg;
  el.hidden = false;
  $("jsonInfo").hidden = true;
}
function showJsonInfo(msg) {
  const el = $("jsonInfo");
  el.textContent = msg;
  el.hidden = false;
  $("jsonError").hidden = true;
}

const REQUIRED_LEGACY_FIELDS = ["name", "text", "x", "y", "fontSize", "color"];
const REQUIRED_LAYER_FIELDS = ["text", "x", "y", "fontSize", "color"];

/** 레이어 하나가 최소 조건(문구 관련 필수 필드)을 만족하는지 검사. */
function validateLayerShape(layer, itemIdx, layerIdx) {
  if (typeof layer !== "object" || layer === null) {
    return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어가 객체가 아닙니다.`;
  }
  if (layer.type === "ink") {
    // 손글씨 레이어는 문구 관련 필수 항목이 필요 없다(자유 형식 획 데이터이므로 형태만 확인).
    return null;
  }
  if (layer.type === "shape") {
    // 도형 레이어는 문구 관련 필수 항목이 필요 없다. 색상 값만 형태를 확인한다(위치/크기는 makeLayer가 기본값으로 채움).
    if ("color" in layer && !isValidColorValue(layer.color)) {
      return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어의 "color"가 올바른 색상 값이 아닙니다(단색 #rrggbb 또는 그라데이션 객체).`;
    }
    return null;
  }
  for (const field of REQUIRED_LAYER_FIELDS) {
    if (!(field in layer)) {
      return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어에 필수 항목 "${field}"가 없습니다.`;
    }
  }
  if (typeof layer.text !== "string") return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어의 "text"가 문자열이 아닙니다.`;
  if (typeof layer.x !== "number" || typeof layer.y !== "number")
    return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어의 위치값(x, y)이 숫자가 아닙니다.`;
  if (typeof layer.fontSize !== "number") return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어의 "fontSize"가 숫자가 아닙니다.`;
  if (!isValidColorValue(layer.color))
    return `${itemIdx + 1}번째 항목의 ${layerIdx + 1}번째 레이어의 "color"가 올바른 색상 값이 아닙니다(단색 #rrggbb 또는 그라데이션 객체).`;
  return null;
}

function validateTemplatesJson(rawText) {
  let parsed;
  try {
    parsed = JSON.parse(rawText);
  } catch (e) {
    return { ok: false, reason: "JSON 문법이 올바르지 않습니다. 가져오기를 취소했습니다." };
  }
  if (!Array.isArray(parsed)) {
    return { ok: false, reason: "최상위 형식이 배열([])이 아닙니다. 가져오기를 취소했습니다." };
  }
  for (let i = 0; i < parsed.length; i++) {
    const item = parsed[i];
    if (typeof item !== "object" || item === null) {
      return { ok: false, reason: `${i + 1}번째 항목이 객체가 아닙니다. 가져오기를 취소했습니다.` };
    }
    if (typeof item.name !== "string" || item.name.trim() === "") {
      return { ok: false, reason: `${i + 1}번째 항목의 "name"이 올바르지 않습니다.` };
    }
    if (Array.isArray(item.layers)) {
      // 새 형식(레이어 배열)
      if (item.layers.length === 0) {
        return { ok: false, reason: `${i + 1}번째 항목의 "layers"가 비어 있습니다.` };
      }
      for (let j = 0; j < item.layers.length; j++) {
        const err = validateLayerShape(item.layers[j], i, j);
        if (err) return { ok: false, reason: err + " 가져오기를 취소했습니다." };
      }
    } else {
      // 예전 형식(평평한 필드 하나 = 레이어 1개)
      for (const field of REQUIRED_LEGACY_FIELDS) {
        if (!(field in item)) {
          return {
            ok: false,
            reason: `${i + 1}번째 항목에 필수 항목 "${field}"가 없습니다. 가져오기를 취소했습니다.`,
          };
        }
      }
      const err = validateLayerShape(item, i, 0);
      if (err) return { ok: false, reason: err + " 가져오기를 취소했습니다." };
    }
  }

  // 정규화: id 없거나 중복되면 새로 부여. layers가 없으면 예전 평평한 필드를 레이어 1개로 감싼다.
  // 레이어별 fontFamily/stroke/rotation/shadow/neon도 없으면 기본값을 채우고(예전 파일 호환),
  // 최상위에 있던 아주 예전 형식의 전역 손글씨 데이터는 손글씨 레이어 하나로 옮겨 담는다.
  const seen = new Set();
  const normalized = parsed.map((item) => {
    let id = item.id;
    if (!id || seen.has(id)) id = uid();
    seen.add(id);
    let layers = (Array.isArray(item.layers) ? item.layers : layersFromLegacyFields(item)).map((l) => makeLayer(l));
    const migratedInk = legacyInkAsLayer(item.ink);
    if (migratedInk) layers = layers.concat([migratedInk]);
    return { id, name: item.name, layers, image: item.image || null, imageName: item.imageName || null, updatedAt: item.updatedAt || new Date().toISOString() };
  });
  return { ok: true, data: normalized };
}

function onImportJson(file) {
  const reader = new FileReader();
  reader.onload = () => {
    const result = validateTemplatesJson(String(reader.result));
    if (!result.ok) {
      showJsonError(result.reason); // 기존 templates 배열은 절대 건드리지 않음
      return;
    }
    templates = result.data;
    saveTemplatesToStorage();
    currentTemplateId = null;
    $("updateTemplateBtn").disabled = true;
    renderTemplateList();
    showJsonInfo(`템플릿 ${templates.length}개를 정상적으로 복원했습니다.`);
  };
  reader.onerror = () => {
    showJsonError("파일을 읽는 중 오류가 발생했습니다. 가져오기를 취소했습니다.");
  };
  reader.readAsText(file);
}

// ---------- 화면 테마(라이트/다크) ----------
// 이미지 합성 결과(캔버스)에는 영향이 없고, 편집기 화면(앱 UI)에만 적용된다.
// 선택한 테마는 이 브라우저의 localStorage에 저장되어 다음에 열어도 유지된다.

const THEME_STORAGE_KEY = "meme-card-theme-v1";

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("themeLightBtn").classList.toggle("active", theme === "light");
  $("themeDarkBtn").classList.toggle("active", theme === "dark");
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (e) {
    /* localStorage를 못 쓰는 환경이어도 화면 전환 자체는 계속 동작하게 둔다 */
  }
}

function loadInitialTheme() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch (e) {
    /* 무시 */
  }
  // 저장된 선택이 없으면 시스템(OS) 설정을 따른다.
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

function bindThemeToggle() {
  $("themeLightBtn").addEventListener("click", () => applyTheme("light"));
  $("themeDarkBtn").addEventListener("click", () => applyTheme("dark"));
}

// ---------- 초기화 ----------

function init() {
  applyTheme(loadInitialTheme());
  bindThemeToggle();
  buildPreviewGrid();
  bindControls();
  syncControlsFromActiveLayer();
  renderLayerChips();
  renderTemplateList();
  renderHistoryList();
  renderAll();
}

document.addEventListener("DOMContentLoaded", init);
