# OG EEG 檢測報告工作台

可重用的 CPU 訊號審閱專案：匿名個案／作息 → 公開或合成示範、CSV 上傳 → 品質遮罩與頻譜 → 可定位片段 → 可列印 PDF、JSON 與原始資料。繁體中文單頁介面，無付費 API、無 GPU。適用於 EEG 技術教學與非臨床訊號審閱；未宣稱任何客戶合作或設備串接。

**技術觀察，待專業確認。** 不偵測疾病，不推論焦慮／壓力／放鬆或療效。示範個案完全虛構，示範 EEG 不對應填寫個案。睜閉眼只標示錄製條件，不當成雜訊。

## 啟動

Python 3.12，建議 2 vCPU、2 GB RAM、1 GB 磁碟（瀏覽器測試另需空間）。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
python -m scripts.prepare_data  # 可選：合法公開 EEG，S001–S008 R01/R02，原始 EDF 約20MB
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

開啟 http://127.0.0.1:8000 。這是本機網址。沒有公開樣本時仍有明示的合成來源。公開預設 S008 R01（睜眼），可切 R02（閉眼）。公開錄製不是即時使用者腦波；設備尚未串接。

```sh
docker compose up --build
```

Docker 非 root，預設只綁 loopback，資料唯讀掛載。健康檢查 `/api/health`。遠端部署由管理者核准目標、HTTPS 與存取政策後執行；不會自動購買資源、改 IAM 或防火牆。

## 操作與資料保護

1. 保留完全虛構個案或選匿名自填。年齡、作息、舒適偏好只在瀏覽器組合，**不送分析 API**。舒適選項不輸出聲光。
2. 選公開／合成來源，或選自己的 CSV。按「產生檢測報告」。修改輸入後舊報告失效，需重新產生才能匯出。
3. 查看四頻帶、原始時序、PSD、每四秒時間—頻率。點遮罩表或證據連結定位原始片段；定位不會重算或修改平均頻譜。
4. 列印／另存 PDF 使用瀏覽器列印視窗。JSON 保留數值、遮罩、規則、來源雜湊與個案背景；原始 CSV 可另下載核對。PDF／JSON 含自填資料，請自行保管。
5. 「清空」釋放目前介面持有的資料。沒有 localStorage、資料庫、共享個案或報告 URL；這不是作業系統等級安全抹除承諾。

上傳只在伺服器記憶體處理，不寫檔、不記錄內容、不傳第三方。分析結果回到本次請求，不提供持久取回。API 回應 `Cache-Control: no-store`。正式公開前仍應由部署者設定 HTTPS、請求速率／並行限制與存取政策，避免上傳不必要個資。

## CSV 契約與數學方法

第一版上傳僅支援 UTF-8 CSV，**不支援 EDF 上傳**。EDF 僅用 MNE 讀取已知公開資料，不自寫 EDF parser。

```csv
time_s,O1_uV,O2_uV
0,10,12
0.00625,11,13
```

上例僅展示欄位，完整檔須 8–120 秒；1–8 EEG 通道、128–512 Hz、時間從零開始且等距（1%容差）、最多8MiB／61440列。通道名為英文字母開頭 `_uV` 結尾，不接受 EOG/ECG/EMG 混入 EEG 平均；單位必須微伏。拒絕 NaN/Inf、重複欄、錯列、非遞增時間與不合理振幅。可先下載示範原始 CSV 作格式參考。

非重疊4秒品質窗，兩秒 Hann／50% overlap Welch PSD，僅去常數均值，無濾波、插值、重參考、ICA 或自動修補。未滿四秒尾段保留原值但不納入統計。平均通過窗 PSD，再平均 EEG 通道。Delta 0.5–4、Theta 4–8、Alpha 8–13、Beta 13–30 Hz；界線採插值積分，相鄰頻帶不重複計功率，分母為0.5–30Hz總功率。不是年齡常模比較。

- Q1：任一通道峰對峰 >200µV，排除整窗平均。
- Q2：任一通道標準差 <0.5µV，排除整窗平均。
- A1：0.5–4 /0.5–45Hz >65% 且峰對峰 >120µV，疑似眼動／慢漂移，僅標記。
- A2：20–45 /0.5–45Hz >50% 且去均值 RMS >10µV，疑似肌電／高頻干擾，僅標記。

A1/A2 是未經臨床驗證的啟發式，沒有 EOG/EMG 不能確認來源。A2 不是 MNE 110–140Hz 肌電算法。所有窗拒絕時不輸出假正常的頻帶值。時間—頻率圖包含全部窗，排除窗加斜線。觀察模板保留規則及片段證據；作息提示只取自自填，不由 EEG 推測。

## 驗證與移交

```sh
python -m pytest -q
python -m playwright install chromium
# 另啟動 uvicorn 後
python tests/ui_check.py
python scripts/verify_deployment.py --base-url http://127.0.0.1:8000
python tests/record_demo.py   # 真實瀏覽器操作無聲 WebM；不錄桌面
python scripts/package_migration.py # 僅已提交來源與明確白名單公開樣本
```

測試涵蓋已知正弦頻帶、功率積分、原值不變、遮罩、條件獨立、全拒絕、輸入邊界、無檔案持久化、個案不傳送、下載與錯誤恢復、360/390/1280/1440px、PDF 列印及無 JS 錯誤。CI 使用標準 GitHub-hosted runner，不保留 artifact、不下載 EEG；部署 workflow 為手動 preflight 範本，未啟用遠端部署。

[來源與授權](docs/SOURCES.md)、[搬遷流程](docs/MIGRATION.md)、[部署說明](docs/DEPLOYMENT.md)。程式 MIT；PhysioNet EEGMMIDB 1.0.0 為 ODC Attribution 1.0，下載腳本及 manifest 保留來源與雜湊。未將原始資料、報告、權重或秘密放入 git。

舊錄製回放／睜閉眼 ML 基線 API 保留相容，**不是目前報告模型**；其小樣本驗證見 [歷史基線紀錄](docs/VALIDATION.md)，不可把舊88.89%當報告或產品準確率。舊 UI 回退標籤 `experience-ui-reviewed-9c8f6cb`。建議公司 repo `ogtech-ai/signal-eeg-experience`，topics `signal,eeg,cpu,demo`。
