# OG EEG 訊號互動 Demo

建議 repository：`ogtech-ai/signal-eeg-experience`；topics：`signal`、`eeg`、`demo`、`cpu`、`fastapi`。適用於公開 EEG 教學、訊號品質展示與輕量模型技術評估；未宣稱與任何客戶合作。

CPU 可運行的獨立研究展示：錄製樣本 → 波形回放 → 選取 4–8 秒 → 品質檢查 → 頻譜特徵／輕量 ML → 場景開合 → JSON 專家摘要。繁體中文、黑白黃介面，不依賴付費 API。

**尚未串接幸福腦設備。不是即時使用者腦波、醫療器材或療效展示。** 場景只映射睜眼／閉眼模型分數，沒有光刺激或音訊控制。人工雜訊在介面及摘要明示。

## 啟動

Python 3.12，CPU；建議 2 vCPU、2 GB RAM、1 GB 可用磁碟（含套件；瀏覽器測試另需空間）。首次訓練在第一次分析時執行，後續快取於記憶體。單程序即可。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
python -m scripts.prepare_data   # 可選：16 個公開基線 EDF，約 20 MB，S001–S008 R01/R02
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

開啟 http://127.0.0.1:8000 。這是本機網址，尚無公開客戶網址。未下載完整公開資料時，預設僅提供清楚標示的合成訊號。下載完成後重新啟動程序，介面自動啟用公開錄製。資料不會上傳。

```sh
docker compose up --build
# 公開資料先由主機 prepare_data 下載；compose 唯讀掛載 ./data
```

Docker 以非 root 使用者執行，僅綁定主機 loopback；健康檢查 `/api/health`。單獨 `docker run --rm -p 127.0.0.1:8000:8000 eeg-demo` 可跑合成模式。正式開放網路前須由 VM 管理者設定經授權的 HTTPS reverse proxy 和存取政策。

## 示範流程

1. 選公開錄製或合成訊號、獨立測試受試者與睜／閉眼條件。
2. 播放波形（原始資料降採樣到 80 Hz 顯示；分析使用 160 Hz），拖曳起點選片段。
3. 點「分析」；Alpha 相對功率、任務分數、場景開合與摘要由同一次計算回傳。
4. 加入人工雜訊後再分析；O1 脈衝使品質門檻失敗，模型停止判讀。波形會呈現實際受污染的分析副本。
5. 下載 JSON 摘要，包含片段數值、品質、資料來源、人工雜訊旗標和測試基線。

## 模型與限制

PhysioNet EEGMMIDB 1.0.0，R01 睜眼、R02 閉眼；O1/Oz/O2 三個枕葉通道。MNE 讀 EDF 並轉為 µV。非重疊 4 秒片段，Welch PSD（2 秒 Hann），4–8 / 8–13 / 13–30 Hz 相對頻帶功率，取 log，StandardScaler + LogisticRegression。沒有重型神經網路、GPU 或外部權重。

訓練 S001–S006；獨立測試 S007–S008，依受試者分割，縮放只 fit 訓練集。每類各一段原始錄製；視窗雖不重疊，仍非獨立受試者。小樣本僅為技術基線，無外部驗證、無信賴區間、機率未校準。展示已接觸測試受試者；後續調參須另保留新測試集。4 秒模型用於 8 秒片段屬展示延伸，未單獨驗證。品質門檻為啟發式：任一通道峰對峰 >200 µV 或標準差 <0.5 µV 即拒絕，並非 autoreject 或臨床品質認證。不映射成壓力、腦損傷或療效。

合成資料依 deterministic seed 產生不同 alpha 振幅，只驗證功能與管線；其準確率不代表真實 EEG 效果。已驗證公開 EEG：品質通過 25/60 測試窗的平衡準確率 88.89%；35 窗被拒絕，且訓練只有 4 位受試者留有可用窗口。詳見驗證紀錄，不能外推成產品成效。公開模式預設 S008 的 12–16 秒品質通過片段，其他位置仍可自由選取。公開資料的實際測試結果由 `prepare_data` 產生於 `data/evaluation.json`，manifest 記錄每份下載 URL 與 SHA-256。請參考 [驗證紀錄](docs/VALIDATION.md)。

## 測試

```sh
python -m pytest -q
python -m playwright install chromium
# 另一終端先啟動 uvicorn
python tests/ui_check.py
```

API 測試涵蓋頻譜、受試者隔離、訊號變化、品質拒絕、人工雜訊與輸入界限。瀏覽器測試涵蓋睜閉眼互動、播放、拒絕、JSON 下載、390px 響應式與 JS 錯誤。截圖只留本機 `artifacts/`。CI 用標準 GitHub-hosted `ubuntu-latest`，10 分鐘上限，不下載 EEG、不保留 Actions artifact；請依組織當前計費與使用量政策確認額度。

## 部署與後續串接

[常駐主機搬遷清單](docs/MIGRATION.md) 與 [VM 部署範本](docs/DEPLOYMENT.md)；目前選定 已指定的常駐 Linux CPU 主機，尚未遠端部署。GitHub Actions `deploy-vm.yml` 僅手動 preflight，缺設定立即失敗，即使填齊仍不執行遠端操作。沒有持久憑證、IAM、防火牆或雲資源變更。

設備介面未提供：未來 adapter 至少需 sample rate、通道名稱、單位、時間戳與資料權限。API 提供未來介接邊界，但本次未承諾設備相容。公開展示不提供任意資料上傳，也不收集個資。

## 授權

Demo 原始碼採 MIT，見 LICENSE。公開 EEG 不含於 git，資料遵循 ODC Attribution 1.0；引用、套件選擇與授權見 [SOURCES.md](docs/SOURCES.md)。未包含客戶提案、私有資料、秘密或外部模型權重。

## 無聲操作錄影

```sh
# 先啟動本機 uvicorn 並下載公開資料
python tests/record_demo.py
ffmpeg -i artifacts/recording/og-eeg-full-operation.webm -an -c:v libx264 -pix_fmt yuv420p -movflags +faststart artifacts/recording/og-eeg-full-operation.mp4
ffprobe -v error -show_streams artifacts/recording/og-eeg-full-operation.mp4
```

錄影腳本實際操作本應用，涵蓋公開／合成來源、播放、片段、分析、品質拒絕與匯出；不是生成動畫。不錄桌面、麥克風或音軌。影片與匯出摘要留在忽略的 artifacts/，不放入程式 repo。公開 EEG 是錄製回放，現場設備未串接。
