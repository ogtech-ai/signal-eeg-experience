"""Memory-only EEG report analysis. Heuristics are not clinical or disease models."""

import csv
import hashlib
import io
import re
import numpy as np
from scipy.signal import welch
from .core import FS, CHANNELS, load_record

VERSION = "eeg-report-rules-1.0"
MAX_BYTES = 8 * 1024 * 1024
MIN_FS, MAX_FS, MIN_SECONDS, MAX_SECONDS, MAX_CHANNELS = 128, 512, 8, 120, 8
BANDS = {"delta": (0.5, 4), "theta": (4, 8), "alpha": (8, 13), "beta": (13, 30)}
RULES = [
    {
        "id": "Q1",
        "label": "振幅超過技術門檻",
        "action": "exclude",
        "definition": "任一通道四秒窗峰對峰 > 200 µV；整窗不納入平均頻譜。",
    },
    {
        "id": "Q2",
        "label": "平坦／低變異訊號",
        "action": "exclude",
        "definition": "任一通道四秒窗標準差 < 0.5 µV；整窗不納入平均頻譜。",
    },
    {
        "id": "A1",
        "label": "疑似眼動／慢漂移",
        "action": "review",
        "definition": "0.5–4 Hz / 0.5–45 Hz 功率 > 65% 且峰對峰 > 120 µV。無 EOG，不能確認眨眼；僅標記，不自動排除。",
    },
    {
        "id": "A2",
        "label": "疑似肌電／高頻干擾",
        "action": "review",
        "definition": "20–45 Hz / 0.5–45 Hz 功率 > 50% 且去均值 RMS > 10 µV。不是已驗證肌電偵測器；僅標記，不自動排除。",
    },
]


def parse_csv(payload):
    if len(payload) > MAX_BYTES:
        raise ValueError("CSV 超過 8 MiB 上限，請截取較短的 EEG 通道資料。")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(
            "請使用 UTF-8 CSV；此版不支援 EDF、壓縮檔或其他二進位格式。"
        ) from error
    if "\x00" in text:
        raise ValueError("檔案不是可讀的 UTF-8 CSV。")
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise ValueError("CSV 是空白或格式不完整。") from error
    if not header or header[0] != "time_s" or not 2 <= len(header) <= MAX_CHANNELS + 1:
        raise ValueError(
            "第一欄必須是 time_s，後接 1–8 個 EEG 通道，例如 O1_uV、Oz_uV、O2_uV。"
        )
    if len(set(header)) != len(header) or any(
        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,15}_uV", h) for h in header[1:]
    ):
        raise ValueError("通道名稱需唯一、以英文字母開頭並以 _uV 結尾；不猜測單位。")
    channels = [h[:-3] for h in header[1:]]
    if any(re.match(r"^(EOG|ECG|EMG)", name, re.I) for name in channels):
        raise ValueError(
            "此版只接受 EEG 通道，請先移除 EOG／ECG／EMG 欄位；不會把它們當成 EEG 平均。"
        )
    rows = []
    try:
        for row_number, row in enumerate(reader, start=2):
            if len(rows) >= MAX_FS * MAX_SECONDS:
                raise ValueError("樣本數超過 61,440 上限。")
            if len(row) != len(header) or any(
                len(v) > 80 or not v.strip() for v in row
            ):
                raise ValueError(f"第 {row_number} 列欄數不符、空值或欄位過長。")
            try:
                values = [float(v) for v in row]
            except ValueError as error:
                raise ValueError(
                    f"第 {row_number} 列含非數值；時間需秒、EEG 需 µV。"
                ) from error
            if not np.isfinite(values).all():
                raise ValueError(
                    f"第 {row_number} 列包含 NaN／Inf，不會自動補值或刪除。"
                )
            if any(abs(v) > 100_000 for v in values[1:]):
                raise ValueError(
                    f"第 {row_number} 列超過 ±100,000 µV，請確認單位與匯出設定。"
                )
            rows.append(values)
    except csv.Error as error:
        raise ValueError("CSV 引號或欄位格式不正確。") from error
    if len(rows) < 2:
        raise ValueError("資料不足；需至少 8 秒等間隔錄製。")
    data = np.asarray(rows, dtype=np.float64)
    intervals = np.diff(data[:, 0])
    dt = float(np.median(intervals))
    if (
        not np.isfinite(intervals).all()
        or not np.isfinite(dt)
        or dt <= 0
        or np.any(intervals <= 0)
        or abs(data[0, 0]) > max(1e-6, dt * 0.01)
    ):
        raise ValueError("time_s 必須從 0 開始且嚴格遞增，不接受重複時間。")
    if np.max(np.abs(intervals - dt)) > max(1e-7, dt * 0.01):
        raise ValueError("時間間隔不一致（容許 1% 誤差）；請先確認缺樣，不會自行插值。")
    fs = round(1 / dt, 6)
    if not MIN_FS <= fs <= MAX_FS:
        raise ValueError(
            "取樣率需為 128–512 Hz，確保 45 Hz 觀察範圍低於 Nyquist 頻率。"
        )
    duration = len(rows) / fs
    if not MIN_SECONDS <= duration <= MAX_SECONDS + 1e-6:
        raise ValueError("錄製長度需為 8–120 秒；請在匯出前截取需要的資料。")
    return data[:, 1:].T.copy(), fs, channels


def demo_record(identifier):
    if identifier in ("public-open", "public-closed"):
        closed = identifier == "public-closed"
        return (
            load_record(8, closed, "physionet"),
            FS,
            CHANNELS,
            {
                "kind": "public",
                "label": f"PhysioNet S008 R0{2 if closed else 1}",
                "condition": "eyes_closed" if closed else "eyes_open",
                "reference": "https://physionet.org/content/eegmmidb/1.0.0/",
                "notice": "公開錄製的三通道子集，不是目前使用者的腦波；ODC Attribution 1.0。",
            },
        )
    if identifier not in ("synthetic-clean", "synthetic-artifacts"):
        raise ValueError("未知示範樣本。")
    fs = 160
    t = np.arange(fs * 40) / fs
    rng = np.random.default_rng(2026)
    x = np.array(
        [
            12 * np.sin(2 * np.pi * (10 + i * 0.15) * t)
            + 4 * np.sin(2 * np.pi * 6 * t)
            + rng.normal(0, 3, len(t))
            for i in range(3)
        ]
    )
    if identifier == "synthetic-artifacts":
        x[0] += 170 * np.exp(-(((t - 9.5) / 0.45) ** 2))
        x[1, (t >= 16) & (t < 20)] += 35 * np.sin(
            2 * np.pi * 35 * t[(t >= 16) & (t < 20)]
        )
        x[0, (t >= 24) & (t < 24.08)] += 350
        x[2, (t >= 32) & (t < 36)] = 0
    return (
        x,
        fs,
        ["Fp1", "Fp2", "O1"],
        {
            "kind": "synthetic",
            "label": "含人工偽跡的合成訊號"
            if identifier.endswith("artifacts")
            else "乾淨合成訊號",
            "condition": "unspecified",
            "reference": "app.reporting.demo_record / seed 2026",
            "notice": "完全合成的功能測試訊號，非真人資料；不能代表偽跡識別效果。",
        },
    )


def band_integral(f, p, lo, hi):
    inside = (f > lo) & (f < hi)
    grid = np.r_[lo, f[inside], hi]
    values = np.r_[np.interp(lo, f, p), p[inside], np.interp(hi, f, p)]
    return float(np.trapezoid(values, grid))


def analyze_report(x, fs, channels, source, raw_sha):
    # Original x is never modified; constant detrend is applied only within Welch.
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] != len(channels) or not np.isfinite(x).all():
        raise ValueError("訊號維度或數值不合法。")
    window_samples = int(round(fs * 4))
    n_windows = x.shape[1] // window_samples
    if n_windows < 2:
        raise ValueError("至少需要兩個完整四秒窗。")
    psds = []
    windows = []
    events = []
    for index in range(n_windows):
        segment = x[:, index * window_samples : (index + 1) * window_samples]
        f, p = welch(
            segment,
            fs,
            window="hann",
            nperseg=int(round(fs * 2)),
            noverlap=int(round(fs)),
            detrend="constant",
            scaling="density",
            axis=-1,
        )
        psds.append(p)
        ptp = np.ptp(segment, axis=1)
        std = np.std(segment, axis=1)
        reasons = []
        for rule, flag in [("Q1", ptp > 200), ("Q2", std < 0.5)]:
            affected = [channels[i] for i in np.flatnonzero(flag)]
            if affected:
                reasons.append({"rule_id": rule, "channels": affected})
        review = []
        for ch, channel in enumerate(channels):
            total = band_integral(f, p[ch], 0.5, 45)
            low = band_integral(f, p[ch], 0.5, 4) / max(total, 1e-12)
            high = band_integral(f, p[ch], 20, 45) / max(total, 1e-12)
            if low > 0.65 and ptp[ch] > 120:
                review.append(("A1", channel, round(low, 4)))
            if high > 0.5 and std[ch] > 10:
                review.append(("A2", channel, round(high, 4)))
        start = index * window_samples / fs
        end = (index + 1) * window_samples / fs
        for reason in reasons:
            events.append(
                {
                    "window": index,
                    "start": start,
                    "end": end,
                    "rule_id": reason["rule_id"],
                    "level": "exclude",
                    "channels": reason["channels"],
                    "evidence": {
                        "peak_to_peak_uv": np.round(ptp, 3).tolist(),
                        "std_uv": np.round(std, 3).tolist(),
                    },
                }
            )
        for rule, channel, ratio in review:
            events.append(
                {
                    "window": index,
                    "start": start,
                    "end": end,
                    "rule_id": rule,
                    "level": "review",
                    "channels": [channel],
                    "evidence": {
                        "power_ratio": ratio,
                        "without_eog_or_emg_confirmation": True,
                    },
                }
            )
        windows.append(
            {
                "index": index,
                "start": start,
                "end": end,
                "included": not bool(reasons),
                "exclude_rules": [r["rule_id"] for r in reasons],
                "review_rules": sorted({r[0] for r in review}),
                "peak_to_peak_uv": np.round(ptp, 3).tolist(),
                "std_uv": np.round(std, 3).tolist(),
            }
        )
    spectra = np.asarray(psds)
    valid = np.array([w["included"] for w in windows])
    accepted = int(valid.sum())
    average = spectra[valid].mean(axis=0) if accepted else None
    band_data = []
    if accepted:
        mean_psd = average.mean(axis=0)
        absolute = [band_integral(f, mean_psd, *bounds) for bounds in BANDS.values()]
        denominator = sum(absolute)
        if denominator <= 1e-12:
            average = None
        else:
            band_data = [
                {
                    "name": name,
                    "low_hz": bounds[0],
                    "high_hz": bounds[1],
                    "power_uv2": power,
                    "relative": power / denominator,
                }
                for (name, bounds), power in zip(BANDS.items(), absolute)
            ]
    observations = [
        {
            "rule_id": "O1",
            "title": "品質與可用範圍",
            "text": f"{n_windows} 個完整四秒窗中，{accepted} 窗納入平均頻譜；其餘 {n_windows-accepted} 窗依 Q1/Q2 技術門檻遮罩。此比例不是健康分數。",
            "evidence_windows": [w["index"] for w in windows if not w["included"]],
        }
    ]
    if band_data:
        largest = max(band_data, key=lambda b: b["relative"])
        observations.append(
            {
                "rule_id": "O2",
                "title": "本次頻帶分布",
                "text": f"在通過窗的 0.5–30 Hz 功率內，{largest['name'].capitalize()} 相對比例為 {largest['relative']*100:.1f}%，高於本次其他頻帶。未使用年齡常模，不能推論放鬆、睡眠或疾病。",
                "evidence_windows": [w["index"] for w in windows if w["included"]],
            }
        )
    else:
        observations.append(
            {
                "rule_id": "O2",
                "title": "暫不產生頻帶結論",
                "text": "沒有足夠且非零的通過窗頻譜；保留原始時序與所有品質標記供專業確認，不以零值冒充頻帶結果。",
                "evidence_windows": [],
            }
        )
    for rule_id, label in [("A1", "疑似眼動／慢漂移"), ("A2", "疑似肌電／高頻干擾")]:
        matches = [e for e in events if e["rule_id"] == rule_id]
        if matches:
            observations.append(
                {
                    "rule_id": rule_id,
                    "title": label,
                    "text": f"有 {len(matches)} 個通道／片段符合啟發式提示，僅供人工複核。沒有 EOG／EMG 輔助，不確認眨眼或肌電來源；這類提示本身不作自動排除。",
                    "evidence_windows": sorted({e["window"] for e in matches}),
                }
            )
    digest = hashlib.sha256(
        (raw_sha + VERSION + source.get("condition", "unspecified")).encode()
    ).hexdigest()[:12]
    freq_mask = (f >= 0.5) & (f <= 45)
    tf_mask = (f >= 0.5) & (f <= 30)
    return {
        "report_id": digest,
        "analysis_version": VERSION,
        "source": source,
        "raw_sha256": raw_sha,
        "sample_rate": fs,
        "nyquist_hz": fs / 2,
        "duration_seconds": x.shape[1] / fs,
        "sample_count": x.shape[1],
        "channels": channels,
        "unit": "µV",
        "signal": x.tolist(),
        "window_seconds": window_samples / fs,
        "windows": windows,
        "events": events,
        "bands": band_data,
        "psd": {
            "frequencies_hz": f[freq_mask].tolist(),
            "power_uv2_hz": average[:, freq_mask].tolist()
            if average is not None
            else None,
        },
        "time_frequency": {
            "frequencies_hz": f[tf_mask].tolist(),
            "window_starts": [w["start"] for w in windows],
            "power_uv2_hz": spectra[:, :, tf_mask].transpose(1, 0, 2).tolist(),
            "includes_excluded_windows": True,
        },
        "quality": {
            "included_windows": accepted,
            "total_windows": n_windows,
            "included_seconds": accepted * window_samples / fs,
            "unscored_tail_seconds": (x.shape[1] - n_windows * window_samples) / fs,
        },
        "observations": observations,
        "rules": RULES,
        "preprocessing": {
            "original_modified": False,
            "window_mask": [bool(v) for v in valid],
            "method": "非重疊四秒品質窗；Welch 使用兩秒 Hann、50% 重疊、每子窗去常數均值；不做濾波、重參考、插值、ICA 或自動修補。先平均通過窗 PSD，再平均 EEG 通道；不拼接排除後的時序。",
            "condition_policy": "睜眼／閉眼只是實驗標籤，不參與品質排除；A1/A2 僅標記。",
            "relative_power_denominator": "四頻帶合計的 0.5–30 Hz 功率；邊界以線性插值積分，頻帶採下界含、上界不含慣例。",
            "tail_policy": "不足四秒的尾段保留於原始訊號，但不納入品質窗或平均 PSD。",
        },
        "limitations": [
            "技術觀察，待專業確認；沒有疾病或焦慮偵測模型，也不預測療效。",
            "無 EOG／EMG，眼動與肌電只能標記為疑似；取樣率與電極位置影響可判讀範圍。",
            "20–45 Hz 提示不是 MNE 110–140 Hz 肌電演算法，不可等同其驗證效果。",
            "頻帶比例不是常模比較，不把閉眼條件當作雜訊或放鬆診斷。",
        ],
    }


def csv_bytes(x, fs, channels):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["time_s"] + [f"{c}_uV" for c in channels])
    for index in range(x.shape[1]):
        writer.writerow(
            [format(index / fs, ".17g")] + [format(v, ".17g") for v in x[:, index]]
        )
    return output.getvalue().encode()
