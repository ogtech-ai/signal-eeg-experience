const $ = (id) => document.getElementById(id);
const state = {
  analysis: null,
  profile: null,
  source: null,
  file: null,
  selected: 0,
  channel: 0,
  generation: 0,
  busy: false,
  dirty: false,
  controller: null,
};
const labels = {
  eyes_open: "睜眼",
  eyes_closed: "閉眼",
  unspecified: "未註明",
};
const ruleLabels = {
  Q1: "振幅超門檻",
  Q2: "平坦訊號",
  A1: "疑似眼動／慢漂移",
  A2: "疑似肌電／高頻干擾",
};
const bandLabels = {
  delta: "Delta",
  theta: "Theta",
  alpha: "Alpha",
  beta: "Beta",
};
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fmt = (n) => Number(n).toFixed(1);
const mobile = matchMedia("(max-width:800px)");
const reduced = matchMedia("(prefers-reduced-motion:reduce)");
function setPhase(text) {
  $("phase").textContent = text;
}
function updateActions() {
  const ready = !!state.analysis && !state.dirty && !state.busy;
  for (const id of ["print-report", "export-json", "download-raw"])
    $(id).disabled = !ready;
  $("generate").disabled =
    state.busy || ($("source").value === "upload" && !state.file);
  $("generate").innerHTML = state.busy
    ? "正在計算頻譜與遮罩…"
    : `產生檢測報告 <span>↗</span>`;
  document.body.classList.toggle("busy", state.busy);
}
function markDirty() {
  state.generation++;
  state.controller?.abort();
  state.busy = false;
  state.dirty = !!state.analysis;
  $("draft-notice").hidden = !state.dirty;
  $("report").classList.toggle("stale", state.dirty);
  setPhase("待產生");
  $("error").textContent = "";
  updateActions();
}
function applyCase() {
  const fictional = $("case-preset").value === "fictional";
  const values = fictional
    ? {
        "case-code": "DEMO-001",
        age: "32",
        sleep: "5.5",
        caffeine: "2",
        "profile-note": "完全虛構的流程示範，不對應任何真人。",
      }
    : { "case-code": "", age: "", sleep: "", caffeine: "", "profile-note": "" };
  for (const [id, value] of Object.entries(values)) {
    $(id).value = value;
    $(id).readOnly = fictional;
  }
  $("shift").checked = false;
  $("shift").disabled = fictional;
  $("case-code").required = !fictional;
  $("profile-editor").open = !fictional;
  $("case-preview").textContent = fictional
    ? "DEMO-001 · 32 歲 · 完全虛構"
    : "使用匿名代號；不填真姓名";
  markDirty();
}
function profile() {
  for (const id of ["case-code", "age", "sleep", "caffeine"])
    if (!$(id).reportValidity())
      throw Error("請確認個案欄位的數值與匿名代號。");
  const numeric = (id) => ($(id).value === "" ? null : Number($(id).value));
  return {
    kind: $("case-preset").value,
    code: $("case-code").value.trim() || "未提供",
    age: numeric("age"),
    sleep_hours: numeric("sleep"),
    caffeine_servings: numeric("caffeine"),
    irregular_schedule: $("shift").checked,
    note: $("profile-note").value.trim(),
    comfort: $("comfort").value,
  };
}
async function responseData(response) {
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("分析服務回應不完整，請稍後再試。");
  }
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "輸入驗證失敗，請檢查格式與實驗條件。",
    );
  return data;
}
async function generate({ automatic = false } = {}) {
  let background;
  try {
    background = profile();
  } catch (error) {
    $("error").textContent = error.message;
    return;
  }
  const source = $("source").value;
  if (source === "upload" && !state.file) {
    $("error").textContent = "請選擇一個符合規格的 CSV，或切回示範資料。";
    return;
  }
  const id = ++state.generation;
  state.controller?.abort();
  state.controller = new AbortController();
  state.busy = true;
  $("error").textContent = "";
  setPhase("分析中");
  updateActions();
  if (!state.analysis) {
    $("loading").hidden = false;
    $("loading").querySelector("strong").textContent = "正在建立檢測報告";
  }
  try {
    const options = { signal: state.controller.signal, cache: "no-store" };
    let response;
    if (source === "upload") {
      response = await fetch(
        `/api/report/upload?condition=${$("condition").value}`,
        {
          ...options,
          method: "POST",
          headers: { "Content-Type": "text/csv" },
          body: state.file,
        },
      );
    } else {
      response = await fetch(
        `/api/report/demo?source=${encodeURIComponent(source)}`,
        options,
      );
    }
    const data = await responseData(response);
    if (id !== state.generation) return;
    state.analysis = data;
    state.profile = background;
    state.source = source;
    state.selected = data.windows.findIndex(
      (w) => !w.included || w.review_rules.length,
    );
    if (state.selected < 0) state.selected = 0;
    state.channel = 0;
    state.dirty = false;
    $("draft-notice").hidden = true;
    $("report").classList.remove("stale");
    $("report").hidden = false;
    $("loading").hidden = true;
    render();
    setPhase("報告已產生");
    if (mobile.matches) {
      $("workflow-details").open = false;
      if (!automatic)
        document
          .querySelector(".report-column")
          .scrollIntoView({
            behavior: reduced.matches ? "auto" : "smooth",
            block: "start",
          });
    }
  } catch (error) {
    if (id !== state.generation || error.name === "AbortError") return;
    $("error").textContent = error.message;
    setPhase("請檢查輸入");
    if (!state.analysis) {
      $("loading").querySelector("strong").textContent = "尚未產生報告";
      $("loading").querySelector("p").textContent =
        "請修正輸入，示範資料始終可以重新選擇。";
    }
  } finally {
    if (id === state.generation) {
      state.busy = false;
      updateActions();
    }
  }
}
function render() {
  const a = state.analysis,
    p = state.profile;
  $("report-id").textContent = `REF ${a.report_id}`;
  $("source-badge").className = `source-badge ${a.source.kind}`;
  $("source-badge").textContent =
    `${a.source.kind === "public" ? "公開錄製回放" : a.source.kind === "synthetic" ? "合成訊號 · 非真人" : "使用者上傳 · 僅本次處理"} / ${a.source.label}`;
  $("preview-label").textContent =
    p.kind === "fictional" ? "完全虛構示範個案" : "自填匿名個案 · 本機組合";
  $("report-case").textContent = p.code;
  $("report-age").textContent =
    `${p.age === null ? "未提供" : p.age + " 歲"} / ${p.kind === "fictional" ? "完全虛構" : "使用者自填"}`;
  $("report-condition").textContent =
    `${labels[a.source.condition]}（實驗標籤）`;
  $("report-routine").textContent =
    `睡眠 ${p.sleep_hours === null ? "未填" : p.sleep_hours + " h"} / 咖啡因 ${p.caffeine_servings === null ? "未填" : p.caffeine_servings + " 份"}`;
  $("profile-context").textContent =
    `${p.kind === "fictional" ? "本個案完全虛構，不對應真人。" : "匿名背景僅在瀏覽器組合，未送往分析 API。"} ${a.source.kind === "upload" ? "上傳數值來源由使用者提供，身份未獨立驗證。" : "目前 EEG 是示範資料，不對應此個案本人，不能作個案結論。"}${p.note ? " 背景：" + p.note : ""}`;
  $("record-info").textContent =
    `${fmt(a.duration_seconds)} 秒 · ${a.sample_rate} Hz · ${a.channels.length} 通道`;
  $("included-count").textContent =
    `${a.quality.included_windows} / ${a.quality.total_windows} 窗`;
  $("included-time").textContent =
    `${fmt(a.quality.included_seconds)} 秒納入平均`;
  $("quality-title").textContent = a.quality.included_windows
    ? "先確認品質，再閱讀頻帶"
    : "暫不提供頻帶結論";
  $("quality-description").textContent =
    `${a.quality.total_windows - a.quality.included_windows} 窗被 Q1/Q2 技術門檻遮罩。疑似眼動／肌電只標記，不自動排除。尾段 ${fmt(a.quality.unscored_tail_seconds)} 秒保留原值、未納入四秒窗統計。`;
  $("bands").innerHTML = a.bands.length
    ? a.bands
        .map(
          (b) =>
            `<div class="band-item"><div><strong>${bandLabels[b.name]}</strong><span>${b.low_hz}–${b.high_hz} Hz</span></div><b>${fmt(b.relative * 100)}<small>%</small></b><div class="band-track"><i style="width:${b.relative * 100}%"></i></div></div>`,
        )
        .join("")
    : '<p class="scope-note">沒有可用的平均頻譜，不以零值假裝頻帶結果。</p>';
  $("channel").innerHTML = a.channels
    .map((c, i) => `<option value="${i}">${esc(c)}</option>`)
    .join("");
  $("window-select").innerHTML = a.windows
    .map(
      (w) =>
        `<option value="${w.index}">${fmt(w.start)}–${fmt(w.end)} s</option>`,
    )
    .join("");
  $("observations").innerHTML = a.observations
    .map(
      (o) =>
        `<div class="observation"><span class="rule-pill">${esc(o.rule_id)}</span><div><h4>${esc(o.title)}</h4><p>${esc(o.text)}</p><div class="evidence-links">${o.evidence_windows
          .slice(0, 8)
          .map(
            (i) =>
              `<button class="evidence-link" data-window="${i}">${fmt(a.windows[i].start)}–${fmt(a.windows[i].end)}s</button>`,
          )
          .join(
            "",
          )}${o.evidence_windows.length > 8 ? '<span class="figure-caption">其餘見完整遮罩</span>' : ""}</div></div></div>`,
    )
    .join("");
  const routine = [];
  if (p.sleep_hours !== null)
    routine.push(
      `自填睡眠 ${p.sleep_hours} 小時／日：可補充錄製當天的作息紀錄供審閱者參考，不由 EEG 推測睡眠不足。`,
    );
  if (p.caffeine_servings !== null)
    routine.push(
      `自填咖啡因 ${p.caffeine_servings} 份／日：可另註最後飲用時間，作為採集背景，不構成飲食或治療處方。`,
    );
  if (p.irregular_schedule)
    routine.push(
      "自填作息不固定／輪班：可補充採集時段與輪班紀錄，不能由頻帶反推。",
    );
  routine.push(
    p.comfort === "quiet"
      ? "舒適度示意偏好：安靜環境；只記錄偏好，不實際播放聲音。"
      : p.comfort === "steady"
        ? "舒適度示意偏好：柔和、常亮環境光；不控制設備、不閃爍。"
        : "舒適度示意偏好：未指定；不輸出聲光。",
  );
  $("routine-notes").innerHTML = routine
    .map((t) => `<p>${esc(t)}</p>`)
    .join("");
  $("window-table").innerHTML = a.windows
    .map((w) => {
      const events = a.events.filter((e) => e.window === w.index);
      const rules = [...new Set(events.map((e) => e.rule_id))];
      const affected = [...new Set(events.flatMap((e) => e.channels))];
      return `<tr data-window="${w.index}" tabindex="0"><td>${fmt(w.start)}–${fmt(w.end)}</td><td>${rules.map((r) => `${r} ${ruleLabels[r]}`).join("；") || "無技術門檻／疑似標記"}</td><td>${esc(affected.join("、") || "—")}<br>全通道最大 PTP ${fmt(Math.max(...w.peak_to_peak_uv))} µV</td><td class="${w.included ? "" : "excluded"}">${w.included ? "納入" : "排除"}</td></tr>`;
    })
    .join("");
  $("preprocessing").textContent =
    a.preprocessing.method +
    " " +
    a.preprocessing.condition_policy +
    " " +
    a.preprocessing.tail_policy;
  $("rule-list").innerHTML = a.rules
    .map(
      (r) =>
        `<li><strong>${esc(r.id)} ${esc(r.label)}</strong>：${esc(r.definition)}</li>`,
    )
    .join("");
  $("limitations").innerHTML = a.limitations
    .map((t) => `<li>${esc(t)}</li>`)
    .join("");
  $("source-reference").textContent =
    `來源：${a.source.label}。${a.source.notice} 參考：${a.source.reference}`;
  $("source-hash").textContent =
    `原始數值／上傳內容 SHA-256：${a.raw_sha256}；報告 ID 不包含個案欄位。`;
  $("analysis-version").textContent = a.analysis_version;
  document.querySelectorAll("[data-window]").forEach((element) => {
    element.onclick = () => selectWindow(Number(element.dataset.window), true);
    element.onkeydown = (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectWindow(Number(element.dataset.window), true);
      }
    };
  });
  selectWindow(state.selected, false);
  $("settings-summary").textContent =
    `${p.kind === "fictional" ? "虛構個案" : "匿名自填"} · ${a.source.kind === "public" ? "公開 EEG" : a.source.kind === "synthetic" ? "合成示範" : "本次 CSV"}`;
  drawAll();
}
function selectWindow(index, scroll) {
  if (!state.analysis) return;
  state.selected = Math.max(
    0,
    Math.min(index, state.analysis.windows.length - 1),
  );
  const w = state.analysis.windows[state.selected];
  $("window-select").value = state.selected;
  $("selected-evidence").textContent =
    `${w.included ? "納入平均" : "排除平均"} · PTP ${state.analysis.channels.map((c, i) => `${c} ${fmt(w.peak_to_peak_uv[i])}`).join(" / ")} µV`;
  $("prev-window").disabled = state.selected === 0;
  $("next-window").disabled =
    state.selected === state.analysis.windows.length - 1;
  document
    .querySelectorAll("#window-table tr")
    .forEach((row) =>
      row.classList.toggle(
        "selected",
        Number(row.dataset.window) === state.selected,
      ),
    );
  drawAll();
  if (scroll)
    $("raw-chart").scrollIntoView({
      behavior: reduced.matches ? "auto" : "smooth",
      block: "center",
    });
}
function canvas(id) {
  const element = $(id),
    w = Math.max(1, element.clientWidth),
    h = Math.max(1, element.clientHeight),
    ratio = Math.min(3, Math.max(2, devicePixelRatio || 1));
  if (
    element.width !== Math.round(w * ratio) ||
    element.height !== Math.round(h * ratio)
  ) {
    element.width = Math.round(w * ratio);
    element.height = Math.round(h * ratio);
  }
  const ctx = element.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.font = "10px -apple-system, sans-serif";
  return { ctx, w, h };
}
function axes(ctx, w, h, { xMin, xMax, yMin, yMax, yLabel, xLabel }) {
  const box = { left: 44, right: w - 10, top: 18, bottom: h - 28 };
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const x = box.left + ((box.right - box.left) * i) / 4,
      y = box.bottom - ((box.bottom - box.top) * i) / 4;
    ctx.strokeStyle = "#e9efe3";
    ctx.beginPath();
    ctx.moveTo(x, box.top);
    ctx.lineTo(x, box.bottom);
    ctx.moveTo(box.left, y);
    ctx.lineTo(box.right, y);
    ctx.stroke();
    ctx.fillStyle = "#8b9e80";
    ctx.textAlign = "center";
    ctx.fillText(fmt(xMin + ((xMax - xMin) * i) / 4), x, h - 10);
    ctx.textAlign = "right";
    ctx.fillText(fmt(yMin + ((yMax - yMin) * i) / 4), box.left - 7, y + 3);
  }
  ctx.fillStyle = "#69886b";
  ctx.textAlign = "left";
  ctx.fillText(yLabel, 4, 10);
  ctx.textAlign = "right";
  ctx.fillText(xLabel, w - 1, h - 1);
  return box;
}
function drawOverview() {
  if (!state.analysis) return;
  const a = state.analysis,
    { ctx, w, h } = canvas("overview"),
    left = 8,
    right = w - 8,
    top = 7,
    bottom = h - 19,
    data = a.signal[state.channel];
  for (const win of a.windows) {
    const x = left + (win.start / a.duration_seconds) * (right - left),
      width = ((win.end - win.start) / a.duration_seconds) * (right - left);
    ctx.fillStyle = win.included ? "#f1f6ed" : "#e9d4b06b";
    ctx.fillRect(x, top, width, bottom - top);
    if (win.review_rules.length) {
      ctx.fillStyle = "#79a4a381";
      ctx.fillRect(x, top, width, 4);
    }
  }
  const scale = Math.max(20, ...data.map(Math.abs)),
    mid = (top + bottom) / 2;
  ctx.strokeStyle = "#5b9480";
  for (let pixel = 0; pixel < right - left; pixel++) {
    const from = Math.floor((pixel / (right - left)) * data.length),
      to = Math.max(
        from + 1,
        Math.floor(((pixel + 1) / (right - left)) * data.length),
      );
    let min = Infinity,
      max = -Infinity;
    for (let i = from; i < to; i++) {
      min = Math.min(min, data[i]);
      max = Math.max(max, data[i]);
    }
    ctx.beginPath();
    ctx.moveTo(left + pixel, mid - (max / scale) * (bottom - top) * 0.43);
    ctx.lineTo(left + pixel, mid - (min / scale) * (bottom - top) * 0.43);
    ctx.stroke();
  }
  const current = a.windows[state.selected];
  ctx.strokeStyle = "#237e62";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(
    left + (current.start / a.duration_seconds) * (right - left),
    top,
    ((current.end - current.start) / a.duration_seconds) * (right - left),
    bottom - top,
  );
  ctx.fillStyle = "#90a184";
  ctx.textAlign = "left";
  ctx.fillText("0s", left, h - 4);
  ctx.textAlign = "right";
  ctx.fillText(`${fmt(a.duration_seconds)}s`, right, h - 4);
}
function drawRaw() {
  if (!state.analysis) return;
  const a = state.analysis,
    win = a.windows[state.selected],
    { ctx, w, h } = canvas("raw-chart"),
    data = a.signal[state.channel].slice(
      Math.round(win.start * a.sample_rate),
      Math.round(win.end * a.sample_rate),
    ),
    max = Math.max(10, Math.ceil(Math.max(...data.map(Math.abs)) / 10) * 10),
    box = axes(ctx, w, h, {
      xMin: win.start,
      xMax: win.end,
      yMin: -max,
      yMax: max,
      yLabel: `${a.channels[state.channel]} · µV 原始值`,
      xLabel: "秒",
    });
  if (!win.included || win.review_rules.length) {
    ctx.fillStyle = win.included ? "#7ba1a111" : "#cfa3611a";
    ctx.fillRect(box.left, box.top, box.right - box.left, box.bottom - box.top);
    ctx.strokeStyle = win.included ? "#7ba1a1" : "#cfa361";
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(
      box.left,
      box.top,
      box.right - box.left,
      box.bottom - box.top,
    );
    ctx.setLineDash([]);
  }
  ctx.strokeStyle = "#287e69";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  data.forEach((value, i) => {
    const x = box.left + (i / (data.length - 1)) * (box.right - box.left),
      y = box.bottom - ((value + max) / (max * 2)) * (box.bottom - box.top);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}
function drawPSD() {
  if (!state.analysis) return;
  const a = state.analysis,
    { ctx, w, h } = canvas("psd-chart"),
    power = a.psd.power_uv2_hz?.[state.channel];
  if (!power) {
    ctx.fillStyle = "#8b9c7e";
    ctx.textAlign = "center";
    ctx.fillText("無通過窗，不產生平均 PSD", w / 2, h / 2);
    return;
  }
  const values = power.map((v) => 10 * Math.log10(Math.max(v, 1e-12))),
    min = Math.floor(Math.min(...values) / 10) * 10,
    max = Math.max(min + 10, Math.ceil(Math.max(...values) / 10) * 10),
    box = axes(ctx, w, h, {
      xMin: 0.5,
      xMax: 45,
      yMin: min,
      yMax: max,
      yLabel: `${a.channels[state.channel]} · dB µV²/Hz`,
      xLabel: "Hz",
    });
  for (const b of Object.values({
    delta: [0.5, 4],
    theta: [4, 8],
    alpha: [8, 13],
    beta: [13, 30],
  })) {
    ctx.fillStyle = "#76a7860b";
    ctx.fillRect(
      box.left + ((b[0] - 0.5) / 44.5) * (box.right - box.left),
      box.top,
      ((b[1] - b[0]) / 44.5) * (box.right - box.left),
      box.bottom - box.top,
    );
  }
  ctx.strokeStyle = "#397f67";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  values.forEach((v, i) => {
    const x =
        box.left +
        ((a.psd.frequencies_hz[i] - 0.5) / 44.5) * (box.right - box.left),
      y = box.bottom - ((v - min) / (max - min)) * (box.bottom - box.top);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}
function drawTF() {
  if (!state.analysis) return;
  const a = state.analysis,
    { ctx, w, h } = canvas("tf-chart"),
    matrix = a.time_frequency.power_uv2_hz[state.channel],
    flat = matrix.flat().map((v) => 10 * Math.log10(Math.max(v, 1e-12))),
    min = Math.min(...flat),
    max = Math.max(min + 1, Math.max(...flat)),
    box = axes(ctx, w, h, {
      xMin: 0,
      xMax: a.windows.at(-1).end,
      yMin: 0.5,
      yMax: 30,
      yLabel: `${a.channels[state.channel]} · Hz`,
      xLabel: "秒",
    }),
    cw = (box.right - box.left) / matrix.length,
    ch = (box.bottom - box.top) / matrix[0].length;
  matrix.forEach((row, i) => {
    row.forEach((p, j) => {
      const ratio = (10 * Math.log10(Math.max(p, 1e-12)) - min) / (max - min);
      ctx.fillStyle = `rgb(${Math.round(240 - 200 * ratio)},${Math.round(247 - 105 * ratio)},${Math.round(232 - 119 * ratio)})`;
      ctx.fillRect(
        box.left + i * cw,
        box.bottom - (j + 1) * ch,
        cw + 0.5,
        ch + 0.5,
      );
    });
    if (!a.windows[i].included) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(box.left + i * cw, box.top, cw, box.bottom - box.top);
      ctx.clip();
      ctx.strokeStyle = "#986a3866";
      ctx.lineWidth = 1;
      for (let y = box.top - 200; y < box.bottom; y += 9) {
        ctx.beginPath();
        ctx.moveTo(box.left + i * cw, y);
        ctx.lineTo(box.left + (i + 1) * cw, y + cw);
        ctx.stroke();
      }
      ctx.restore();
    }
  });
  ctx.strokeStyle = "#244c35";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(
    box.left + state.selected * cw,
    box.top,
    cw,
    box.bottom - box.top,
  );
  ctx.fillStyle = "#6c8568";
  ctx.textAlign = "right";
  ctx.fillText(`色階 ${fmt(min)} 至 ${fmt(max)} dB`, w - 4, 10);
}
function drawAll() {
  if (!state.analysis || $("report").hidden) return;
  drawOverview();
  drawRaw();
  drawPSD();
  drawTF();
}
function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
function chooseFile(file) {
  markDirty();
  state.file = null;
  $("file-name").textContent = "尚未選取檔案";
  if (!file) {
    updateActions();
    return;
  }
  if (!file.name.toLowerCase().endsWith(".csv")) {
    $("error").textContent = "此版只支援 UTF-8 CSV；不接受 EDF 或壓縮檔。";
    $("eeg-file").value = "";
    updateActions();
    return;
  }
  if (file.size > 8 * 1024 * 1024) {
    $("error").textContent = "檔案超過 8 MiB，請先截取需要的錄製。";
    $("eeg-file").value = "";
    updateActions();
    return;
  }
  state.file = file;
  $("file-name").textContent =
    `${file.name} · ${(file.size / 1024).toFixed(1)} KiB（僅本機顯示檔名）`;
  updateActions();
}
$("case-preset").onchange = applyCase;
for (const id of [
  "case-code",
  "age",
  "sleep",
  "caffeine",
  "shift",
  "profile-note",
  "comfort",
  "condition",
])
  $(id).addEventListener("input", () => {
    markDirty();
    $("case-preview").textContent =
      $("case-preset").value === "fictional"
        ? "DEMO-001 · 完全虛構"
        : `${$("case-code").value.trim() || "匿名代號未填"} · 使用者自填`;
  });
$("source").onchange = () => {
  markDirty();
  $("upload-box").hidden = $("source").value !== "upload";
  updateActions();
};
$("eeg-file").onchange = (event) => chooseFile(event.target.files[0]);
$("generate").onclick = () => generate();
$("channel").onchange = () => {
  state.channel = Number($("channel").value);
  selectWindow(state.selected, false);
};
$("window-select").onchange = () =>
  selectWindow(Number($("window-select").value), false);
$("prev-window").onclick = () => selectWindow(state.selected - 1, false);
$("next-window").onclick = () => selectWindow(state.selected + 1, false);
$("overview").onclick = (event) => {
  if (!state.analysis || state.dirty) return;
  const rect = $("overview").getBoundingClientRect(),
    time =
      Math.max(
        0,
        Math.min(1, (event.clientX - rect.left - 8) / (rect.width - 16)),
      ) * state.analysis.duration_seconds;
  selectWindow(Math.floor(time / state.analysis.window_seconds), false);
};
$("tf-chart").onclick = (event) => {
  if (!state.analysis || state.dirty) return;
  const rect = $("tf-chart").getBoundingClientRect(),
    index = Math.floor(
      Math.max(
        0,
        Math.min(0.999, (event.clientX - rect.left - 44) / (rect.width - 54)),
      ) * state.analysis.windows.length,
    );
  selectWindow(index, false);
};
$("print-report").onclick = () => {
  if (state.analysis && !state.dirty && !state.busy) {
    drawAll();
    window.print();
  }
};
$("export-json").onclick = () => {
  if (state.analysis && !state.dirty)
    download(
      new Blob(
        [
          JSON.stringify(
            {
              case_background: state.profile,
              analysis: state.analysis,
              view: {
                channel: state.analysis.channels[state.channel],
                window: state.selected,
              },
            },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
      `EEG-report-${state.analysis.report_id}.json`,
    );
};
$("download-raw").onclick = async () => {
  if (!state.analysis || state.dirty) return;
  if (state.source === "upload" && state.file) {
    download(state.file, "eeg-original.csv");
    return;
  }
  try {
    const r = await fetch(`/api/report/demo.csv?source=${state.source}`, {
      cache: "no-store",
    });
    if (!r.ok) throw Error("無法下載示範原始資料");
    download(await r.blob(), "eeg-original.csv");
  } catch (error) {
    $("error").textContent = error.message;
  }
};
$("sample-csv").onclick = async () => {
  try {
    const r = await fetch("/api/report/demo.csv?source=synthetic-artifacts", {
      cache: "no-store",
    });
    if (!r.ok) throw Error("示範 CSV 暫時無法下載");
    download(await r.blob(), "eeg-synthetic-example.csv");
  } catch (error) {
    $("error").textContent = error.message;
  }
};
$("clear-session").onclick = () => {
  state.generation++;
  state.controller?.abort();
  state.analysis = null;
  state.profile = null;
  state.source = null;
  state.file = null;
  state.busy = false;
  state.dirty = false;
  $("eeg-file").value = "";
  $("file-name").textContent = "尚未選取檔案";
  $("case-preset").value = "fictional";
  applyCase();
  $("comfort").value = "none";
  $("condition").value = "unspecified";
  $("source").value = $("source").querySelector('option[value="public-open"]')
    .disabled
    ? "synthetic-artifacts"
    : "public-open";
  $("upload-box").hidden = true;
  $("report").hidden = true;
  $("draft-notice").hidden = true;
  $("loading").hidden = false;
  $("loading").querySelector("strong").textContent = "本次資料已清除";
  $("loading").querySelector("p").textContent =
    "重新選擇示範資料或上傳 CSV，即可建立下一份報告。";
  $("workflow-details").open = true;
  setPhase("已清除");
  updateActions();
};
window.addEventListener("beforeprint", drawAll);
window.addEventListener("resize", drawAll);
new ResizeObserver(drawAll).observe(document.querySelector(".report-column"));
mobile.addEventListener("change", () => {
  $("workflow-details").open = !mobile.matches || !state.analysis;
});
fetch("/api/report/catalog", { cache: "no-store" })
  .then(responseData)
  .then((c) => {
    for (const item of c.sources) {
      const option = $("source").querySelector(`option[value="${item.id}"]`);
      option.disabled = !item.available;
      option.textContent = item.label + (item.available ? "" : "（未下載）");
    }
    $("source").value = c.public_available
      ? "public-open"
      : "synthetic-artifacts";
    generate({ automatic: true });
  })
  .catch((error) => {
    $("error").textContent = error.message;
    setPhase("服務未就緒");
    updateActions();
  });
