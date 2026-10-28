const $ = (id) => document.getElementById(id);
const state = {
  closed: false,
  record: null,
  result: null,
  started: false,
  playing: false,
  position: 0,
  generation: 0,
  phase: "loading",
  lastFrame: 0,
  raf: 0,
  timer: 0,
};
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
const phaseNames = {
  loading: "正在載入",
  ready: "等待分析",
  analyzing: "分析中…",
  accepted: "品質通過",
  rejected: "品質未通過",
  stale: "片段已變更",
  error: "分析失敗",
};
const clock = (seconds) =>
  `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "無法完成分析，請重新選擇片段。",
    );
  return data;
}
function setPhase(phase) {
  state.phase = phase;
  $("scene").dataset.state = phase;
  $("status").textContent = phaseNames[phase];
  $("analyze").disabled =
    !state.record || phase === "loading" || phase === "analyzing";
  $("play").disabled = !state.record || phase === "loading";
  $("scene-play").disabled = !state.record || phase === "loading";
  $("start").disabled = !state.record || phase === "loading";
  $("scene-mode").textContent =
    phase === "accepted"
      ? "模型結果已連動"
      : phase === "rejected"
        ? "已停止判讀"
        : phase === "analyzing"
          ? "品質檢查 → 模型推論"
          : phase === "stale"
            ? "等待重新分析"
            : "錄製樣本 · 非即時量測";
  $("analyze-label").textContent = !state.started
    ? "開始體驗"
    : phase === "analyzing"
      ? "分析中…"
      : phase === "stale"
        ? "分析新片段"
        : "重新分析";
}
function resetEvidence() {
  state.result = null;
  $("view-response").hidden = true;
  $("wave-title").textContent = "錄製訊號";
  $("copy-note").hidden = true;
  $("download").disabled = true;
  $("probability").innerHTML = "—<small>%</small>";
  $("probability-fill").style.transition = "none";
  $("probability-fill").style.width = "0%";
  document.querySelector(".probability-track").classList.add("inactive");
  $("display-range").textContent = "顯示範圍 ±100 µV";
  $("probability-pin").style.opacity = 0;
  $("quality-indicator").className = "quality-indicator";
  $("quality-count").textContent = "— / 3";
  $("quality").textContent = "分析後確認三通道訊號品質。";
  $("channel-quality").innerHTML = ["O1", "Oz", "O2"]
    .map((c) => `<span>${c} <i>—</i></span>`)
    .join("");
  $("score").textContent = "分類任務分數，並非情緒或健康指標。";
  $("latency").textContent = "CPU 推論";
  $("baseline-accuracy").textContent = "—";
  $("baseline-coverage").textContent = "—";
  $("bands").innerHTML = "<p>分析後顯示 4–30 Hz 頻帶功率比例。</p>";
  $("metrics").textContent = "小樣本研究基線，不代表設備或整體產品成效。";
  $("summary").textContent = "目前選取的片段尚未分析。";
  $("review-label").textContent = "目前片段尚未分析";
  $("scene-paused").hidden = true;
  $("scene-intro").hidden = state.started;
  $("prediction").textContent = state.started ? "等待重新分析" : "準備就緒";
  $("response-note").textContent = "視窗開合將由閉眼任務分數控制";
  $("scene").style.setProperty("--opening", "43%");
}
function invalidate() {
  state.generation++;
  clearTimeout(state.timer);
  resetEvidence();
  setPhase(state.record ? "stale" : "loading");
}
function updateSelection() {
  const start = Number($("start").value),
    duration = Number($("duration").value),
    total = state.record?.duration || 60;
  $("time").textContent = `${clock(start)} — ${clock(start + duration)}`;
  $("total-time").textContent = clock(total);
  $("end-time").textContent = clock(total);
  $("start").style.left = "-5.5px";
  $("start").style.right = "auto";
  $("start").style.width =
    `calc(${((total - duration) / total) * 100}% + 11px)`;
  $("segment-label").textContent = `${duration} 秒片段循環回放`;
  $("playback-note").textContent =
    `${duration} 秒片段循環回放；分數為整段分析結果，不隨波峰即時重算。`;
  $("cursor").textContent =
    `${(start + (state.position % duration)).toFixed(1)} 秒`;
  $("restore").hidden = !$("artifact").checked;
}
async function load() {
  setPlaying(false);
  state.record = null;
  state.position = 0;
  invalidate();
  const id = state.generation;
  $("error").textContent = "";
  $("provenance").textContent = "正在載入樣本…";
  try {
    const record = await api(
      `/api/record?source=${$("source").value}&subject=${$("subject").value}&closed=${state.closed}`,
    );
    if (id !== state.generation) return;
    state.record = record;
    $("start").max = Math.floor(record.duration - Number($("duration").value));
    $("start").value =
      record.source === "physionet" && record.subject === 8 ? 12 : 0;
    $("provenance").textContent =
      `${record.source === "synthetic" ? "合成訊號 · 非真人腦波" : "PhysioNet 公開 EEG 回放"} / ${record.label} / S00${record.subject}`;
    $("open").querySelector("span").textContent =
      record.source === "physionet" ? "R01 · 睜眼基線" : "合成 · 睜眼模式";
    $("closed").querySelector("span").textContent =
      record.source === "physionet" ? "R02 · 閉眼基線" : "合成 · 閉眼模式";
    $("sample-caption").textContent =
      record.source === "synthetic"
        ? "程式產生的功能測試訊號，並非真人腦波。"
        : "公開受試者的錄製，並非目前使用者的腦波。";
    document.querySelector(".replay-label").innerHTML =
      `<span class="tiny-wave">∿</span> ${record.source === "synthetic" ? "合成訊號模式" : "公開錄製回放"}`;
    updateSelection();
    setPhase("ready");
    drawAll();
    if (state.started) await analyze();
  } catch (error) {
    if (id !== state.generation) return;
    state.record = null;
    setPhase("error");
    $("scene-intro").hidden = true;
    $("prediction").textContent = "樣本暫時不可用";
    $("response-note").textContent = "請重新選擇樣本或稍後再試";
    $("error").textContent = error.message;
    drawAll();
  }
}
async function analyze({ play = false } = {}) {
  if (!state.record) return;
  clearTimeout(state.timer);
  state.started = true;
  $("first-use").classList.add("started");
  $("first-use").querySelector(".guide-title").textContent = "接著試試";
  const id = ++state.generation;
  resetEvidence();
  setPhase("analyzing");
  $("error").textContent = "";
  $("scene-intro").hidden = true;
  $("prediction").textContent = "正在讀取訊號";
  $("response-note").textContent = "先確認品質，再計算模型結果";
  if (play) setPlaying(true);
  const request = {
    source: $("source").value,
    subject: Number($("subject").value),
    closed: state.closed,
    start: Number($("start").value),
    duration: Number($("duration").value),
    artifact: $("artifact").checked,
  };
  try {
    const data = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (id !== state.generation) return;
    state.result = data;
    renderResult(data);
    drawAll();
  } catch (error) {
    if (id !== state.generation) return;
    setPlaying(false);
    setPhase("error");
    $("prediction").textContent = "暫時無法分析";
    $("response-note").textContent = "請重新選取片段或切換樣本";
    $("error").textContent = error.message;
  }
}
function renderResult(data) {
  const accepted = data.quality.accepted,
    p = data.closed_probability;
  setPhase(accepted ? "accepted" : "rejected");
  if (!accepted) setPlaying(false);
  $("prediction").textContent = accepted
    ? p >= 0.5
      ? "視野收合"
      : "視野展開"
    : "暫停判讀";
  $("response-note").textContent = accepted
    ? `模型偏向${data.prediction} · 視窗開合依任務分數映射`
    : "原始資料未改變，僅停止這次的分類";
  $("scene-paused").hidden = accepted;
  $("scene").style.setProperty(
    "--opening",
    accepted ? `${46 - 35 * p}%` : "19%",
  );
  $("quality-indicator").className =
    `quality-indicator ${accepted ? "accepted" : "rejected"}`;
  $("quality-count").textContent =
    `${3 - data.quality.bad_channels.length} / 3`;
  $("quality").textContent = accepted
    ? "三通道通過目前的品質門檻。"
    : `${data.quality.bad_channels.join("、")} 未通過門檻，這次不提供分類。`;
  $("channel-quality").innerHTML = ["O1", "Oz", "O2"]
    .map((c, i) => {
      const bad = data.quality.bad_channels.includes(c);
      return `<span class="${bad ? "bad" : "good"}" title="峰對峰 ${data.quality.peak_to_peak_uv[i]} µV">${c} <i>${bad ? "!" : "✓"}</i></span>`;
    })
    .join("");
  $("probability").innerHTML =
    p === null
      ? "—<small>%</small>"
      : `${(p * 100).toFixed(1)}<small>%</small>`;
  $("probability-fill").style.transition = p === null ? "none" : "width .7s";
  document
    .querySelector(".probability-track")
    .classList.toggle("inactive", p === null);
  $("probability-fill").style.width = p === null ? "0%" : `${p * 100}%`;
  $("display-range").textContent = data.segment_signal.some((channel) =>
    channel.some((value) => Math.abs(value) > 105),
  )
    ? "±100 µV · △ 超出顯示範圍"
    : "顯示範圍 ±100 µV";
  $("probability-pin").style.left =
    p === null ? "0%" : `calc(${p * 100}% - 5px)`;
  $("probability-pin").style.opacity = p === null ? 0 : 1;
  $("score").textContent = accepted
    ? "分數只代表睜眼／閉眼任務，不代表放鬆程度。"
    : "品質未通過，任務分數與視覺回應皆已暫停。";
  $("latency").textContent = `${Math.round(data.elapsed_ms)} ms`;
  $("bands").innerHTML = Object.entries(data.bands)
    .map(
      ([key, value]) =>
        `<div class="bar-row ${key}"><span>${{ theta: "Theta · 4–8", alpha: "Alpha · 8–13", beta: "Beta · 13–30" }[key]} Hz</span><div class="bar"><i style="width:${value * 100}%"></i></div><span>${(value * 100).toFixed(1)}%</span></div>`,
    )
    .join("");
  const m = data.evaluation;
  $("baseline-accuracy").textContent =
    `${(m.balanced_accuracy * 100).toFixed(1)}%`;
  $("baseline-coverage").textContent =
    `${m.test_windows} / ${m.test_total_windows}`;
  $("metrics").textContent =
    `${m.source === "synthetic" ? "合成訊號功能測試，不能代表真實 EEG 成效。" : "公開 EEG 小樣本基線；準確率僅針對通過品質門檻的測試窗。"}\n訓練規劃 S001–S006；實際有效受試者 ${m.effective_train_subjects.join("、")}。獨立測試 S007–S008。\n混淆矩陣（睜眼、閉眼）：${JSON.stringify(m.confusion_matrix)}。\n目前片段峰對峰：${data.quality.peak_to_peak_uv.join(" / ")} µV；任一通道 >200 µV 或標準差 <0.5 µV 即拒絕。\n模型分數未校準，不能解讀成疾病、壓力或療效。`;
  $("summary").textContent = data.summary;
  $("review-label").textContent =
    `${accepted ? "品質通過" : "品質未通過"} · ${clock(data.request.start)}–${clock(data.request.start + data.request.duration)} · 可匯出`;
  $("download").disabled = false;
  $("wave-title").textContent = data.artifact_injected
    ? "分析副本：含人工雜訊"
    : "錄製訊號";
  $("copy-note").hidden = !data.artifact_injected;
  $("jump-summary").textContent = accepted
    ? `品質通過 · 閉眼任務分數 ${(p * 100).toFixed(1)}%`
    : "品質未通過 · 分類與回應已暫停";
  $("view-response").classList.toggle("rejected", !accepted);
  $("view-response").hidden = false;
  updateSelection();
}
function fitCanvas(canvas) {
  const ratio = Math.min(devicePixelRatio || 1, 2),
    width = Math.max(1, canvas.clientWidth),
    height = Math.max(1, canvas.clientHeight);
  if (
    canvas.width !== Math.round(width * ratio) ||
    canvas.height !== Math.round(height * ratio)
  ) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return { ctx, w: width, h: height };
}
function drawWave() {
  const { ctx, w, h } = fitCanvas($("wave"));
  if (!state.record) return;
  const left = 42,
    right = w - 11,
    top = 11,
    bottom = h - 25,
    row = (bottom - top) / 3,
    start = Number($("start").value),
    duration = Number($("duration").value);
  const data = state.result?.segment_signal || state.record.signal,
    fs = state.result?.sample_rate || state.record.sample_rate,
    offset = state.result ? 0 : Math.floor(start * fs),
    n = Math.floor(duration * fs);
  ctx.font = "10px -apple-system, sans-serif";
  for (let t = 0; t <= 4; t++) {
    const x = left + ((right - left) * t) / 4;
    ctx.strokeStyle = "#eef2ed";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.fillStyle = "#8d9b91";
    ctx.textAlign = t === 4 ? "right" : t === 0 ? "left" : "center";
    ctx.fillText(
      `${(start + (duration * t) / 4).toFixed(duration === 4 ? 0 : 0)}s`,
      x,
      h - 7,
    );
  }
  for (let ch = 0; ch < 3; ch++) {
    const mid = top + row * (ch + 0.5),
      scale = (row * 0.43) / 100;
    ctx.textAlign = "left";
    ctx.fillStyle = "#789486";
    ctx.font = "10px ui-monospace, monospace";
    ctx.fillText(["O1", "Oz", "O2"][ch], 7, mid + 3);
    ctx.strokeStyle = "#e2eae2";
    ctx.beginPath();
    ctx.moveTo(left, mid);
    ctx.lineTo(right, mid);
    ctx.stroke();
    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top + row * ch, right - left, row);
    ctx.clip();
    ctx.strokeStyle = ["#278d8b", "#62a397", "#94b4a2"][ch];
    ctx.lineWidth = 1.15;
    ctx.beginPath();
    let clipped = false;
    for (let i = 0; i < n; i++) {
      const value = data[ch][offset + i] || 0,
        x = left + (i / (n - 1)) * (right - left),
        y = mid - Math.max(-105, Math.min(105, value)) * scale;
      clipped = clipped || Math.abs(value) > 105;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
    if (clipped) {
      ctx.fillStyle = "#b48a48";
      ctx.beginPath();
      ctx.moveTo(right - 7, mid - row * 0.4);
      ctx.lineTo(right - 1, mid - row * 0.4);
      ctx.lineTo(right - 4, mid - row * 0.4 + 5);
      ctx.fill();
    }
  }
  if (state.playing) {
    const x = left + ((state.position % duration) / duration) * (right - left);
    ctx.strokeStyle = "#1a827b77";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();
    ctx.fillStyle = "#1a827b";
    ctx.beginPath();
    ctx.arc(x, top, 2, 0, Math.PI * 2);
    ctx.fill();
  }
  $("cursor").textContent =
    `${(start + (state.position % duration)).toFixed(1)} 秒`;
}
function drawOverview() {
  const { ctx, w, h } = fitCanvas($("overview"));
  if (!state.record) return;
  const total = state.record.duration,
    start = Number($("start").value),
    duration = Number($("duration").value),
    data = state.record.signal[0],
    x0 = (start / total) * w,
    x1 = ((start + duration) / total) * w;
  ctx.fillStyle = "#f0f4ee";
  ctx.fillRect(0, h / 2 - 5, w, 10);
  ctx.fillStyle = "#a6c9b8";
  ctx.fillRect(x0, 2, Math.max(x1 - x0, 2), h - 4);
  for (let x = 0; x < w; x += 2) {
    const index = Math.floor((x / w) * data.length),
      value = Math.min(8, Math.abs(data[index] || 0) * 0.08 + 1);
    ctx.strokeStyle = x >= x0 && x <= x1 ? "#3a8d7e" : "#c4d4c7";
    ctx.beginPath();
    ctx.moveTo(x, h / 2 - value);
    ctx.lineTo(x, h / 2 + value);
    ctx.stroke();
  }
  ctx.strokeStyle = "#4c9a87";
  ctx.beginPath();
  ctx.moveTo(x0, 1);
  ctx.lineTo(x0, h - 1);
  ctx.moveTo(x1, 1);
  ctx.lineTo(x1, h - 1);
  ctx.stroke();
}
function drawLandscape() {
  const { ctx, w, h } = fitCanvas($("landscape"));
  const sky = ctx.createLinearGradient(0, 0, 0, h);
  sky.addColorStop(0, "#b4d4d5");
  sky.addColorStop(0.46, "#eee9d9");
  sky.addColorStop(0.52, "#c3d9d4");
  sky.addColorStop(1, "#6ca6a3");
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, w, h);
  const sunX = w * 0.72,
    sunY = h * 0.25,
    glow = ctx.createRadialGradient(sunX, sunY, 2, sunX, sunY, w * 0.26);
  glow.addColorStop(0, "#fff8dfd9");
  glow.addColorStop(0.23, "#fcf2d39c");
  glow.addColorStop(1, "#fcf2d300");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = "#f9f0d4";
  ctx.beginPath();
  ctx.arc(sunX, sunY, 14, 0, Math.PI * 2);
  ctx.fill();
  function mountain(color, y, points) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(0, h);
    ctx.lineTo(0, y * h);
    for (let i = 0; i < points.length; i += 6)
      ctx.bezierCurveTo(
        points[i] * w,
        points[i + 1] * h,
        points[i + 2] * w,
        points[i + 3] * h,
        points[i + 4] * w,
        points[i + 5] * h,
      );
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fill();
  }
  mountain(
    "#8dabad",
    0.44,
    [
      0.1, 0.27, 0.13, 0.36, 0.23, 0.34, 0.34, 0.32, 0.35, 0.48, 0.45, 0.44,
      0.6, 0.4, 0.64, 0.33, 0.74, 0.37, 0.85, 0.4, 0.9, 0.33, 1, 0.42,
    ],
  );
  mountain(
    "#5e8e92",
    0.46,
    [
      0.05, 0.4, 0.1, 0.45, 0.17, 0.4, 0.25, 0.35, 0.3, 0.47, 0.4, 0.47, 0.57,
      0.48, 0.58, 0.4, 0.7, 0.45, 0.82, 0.49, 0.89, 0.38, 1, 0.44,
    ],
  );
  const lake = ctx.createLinearGradient(0, h * 0.49, 0, h);
  lake.addColorStop(0, "#c5dbd3");
  lake.addColorStop(0.3, "#a1c5bf");
  lake.addColorStop(1, "#3b7d84");
  ctx.fillStyle = lake;
  ctx.fillRect(0, h * 0.49, w, h * 0.51);
  const phase =
    state.playing && state.phase === "accepted" && !reducedMotion.matches
      ? state.position * 0.8
      : 0;
  for (let i = 0; i < 28; i++) {
    const y = h * (0.5 + i * 0.017),
      spread = 20 + i * 5,
      center = sunX + Math.sin(i * 1.6 + phase) * spread * 0.2;
    ctx.strokeStyle = i % 3 === 0 ? "#f3ecd280" : "#e1eee943";
    ctx.lineWidth = 0.6 + i * 0.025;
    ctx.beginPath();
    ctx.moveTo(center - spread, y);
    ctx.bezierCurveTo(
      center - spread * 0.3,
      y + Math.sin(i + phase) * 1.7,
      center + spread * 0.4,
      y - 1,
      center + spread,
      y,
    );
    ctx.stroke();
    const shift = (i * 71) % w;
    ctx.strokeStyle = "#1e677e24";
    ctx.beginPath();
    ctx.moveTo(shift, y + 5);
    ctx.lineTo(Math.min(w, shift + 40 + i * 2), y + 5);
    ctx.stroke();
  }
  mountain(
    "#356c70",
    0.78,
    [
      0.07, 0.76, 0.1, 0.68, 0.16, 0.72, 0.2, 0.72, 0.2, 0.84, 0.28, 0.84, 0.35,
      0.88, 0.38, 0.94, 0.47, 1, 0.6, 1, 0.79, 0.89, 0.84, 0.88, 0.93, 0.8,
      0.94, 0.8, 1, 0.86,
    ],
  );
  mountain(
    "#204f59",
    0.89,
    [
      0.04, 0.82, 0.07, 0.77, 0.13, 0.8, 0.17, 0.82, 0.15, 0.92, 0.27, 0.96,
      0.45, 1, 0.57, 1, 0.67, 1, 0.82, 0.94, 0.84, 0.92, 0.92, 0.94, 1, 0.92, 1,
      0.92, 1, 1, 1, 1,
    ],
  );
}
function drawAll() {
  drawWave();
  drawOverview();
  drawLandscape();
}
function frame(t) {
  if (!state.playing) return;
  state.position += (t - state.lastFrame) / 1000;
  state.lastFrame = t;
  drawWave();
  drawLandscape();
  state.raf = requestAnimationFrame(frame);
}
function setPlaying(value) {
  cancelAnimationFrame(state.raf);
  state.playing = value;
  $("play").innerHTML = `<span>${value ? "Ⅱ" : "▶"}</span>`;
  $("play").setAttribute("aria-label", value ? "暫停錄製" : "播放錄製");
  $("scene-play").textContent = value ? "Ⅱ 暫停" : "▶ 回放";
  $("scene-play").setAttribute("aria-label", value ? "暫停錄製" : "播放錄製");
  if (value) {
    state.lastFrame = performance.now();
    state.raf = requestAnimationFrame(frame);
  } else if (state.record) drawAll();
}
function queueAnalysis() {
  clearTimeout(state.timer);
  if (state.started && state.record)
    state.timer = setTimeout(() => analyze(), 180);
}
function choose(value) {
  state.closed = value;
  $("open").setAttribute("aria-pressed", !value);
  $("closed").setAttribute("aria-pressed", value);
  load();
}
$("open").onclick = () => choose(false);
$("closed").onclick = () => choose(true);
$("source").onchange = load;
$("subject").onchange = load;
$("start").oninput = () => {
  state.position = 0;
  invalidate();
  updateSelection();
  drawAll();
};
$("start").onchange = queueAnalysis;
$("duration").onchange = () => {
  if (!state.record) return;
  invalidate();
  $("start").max = Math.floor(
    state.record.duration - Number($("duration").value),
  );
  $("start").value = Math.min(Number($("start").value), Number($("start").max));
  state.position = 0;
  updateSelection();
  drawAll();
  queueAnalysis();
};
$("artifact").onchange = () => {
  invalidate();
  updateSelection();
  drawAll();
  if (state.started) analyze();
};
$("restore").onclick = () => {
  $("artifact").checked = false;
  $("artifact").onchange();
};
$("view-response").onclick = () => {
  $("scene").scrollIntoView({
    behavior: reducedMotion.matches ? "auto" : "smooth",
    block: "start",
  });
  $("scene").focus({ preventScroll: true });
};
$("scene-play").onclick = () => {
  if (state.record) setPlaying(!state.playing);
};
$("play").onclick = () => {
  if (state.record) setPlaying(!state.playing);
};
$("analyze").onclick = () => analyze({ play: !state.started });
$("download").onclick = () => {
  if (!state.result) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(state.result, null, 2)], {
      type: "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "og-eeg-review.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
const compactLayout = matchMedia("(max-width: 720px)");
function positionTimeline() {
  const timeline = document.querySelector(".timeline");
  const experience = document.querySelector(".experience");
  if (compactLayout.matches && timeline.parentElement !== experience)
    experience.append(timeline);
  else if (!compactLayout.matches && timeline.parentElement === experience)
    document.querySelector(".workbench").after(timeline);
  drawAll();
}
compactLayout.addEventListener("change", positionTimeline);
positionTimeline();
new ResizeObserver(() => drawAll()).observe(
  document.querySelector(".experience"),
);
window.addEventListener("resize", drawAll);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) setPlaying(false);
});
api("/api/catalog")
  .then((c) => {
    if (c.public_available) {
      const option = $("source").options[1];
      option.disabled = false;
      option.textContent = "PhysioNet · 公開 EEG 錄製";
      $("source").value = "physionet";
      $("subject").value = "8";
    }
    load();
  })
  .catch((error) => {
    setPhase("error");
    $("error").textContent = error.message;
  });
