# 常駐開發主機搬遷準備

選定目標：已指定的常駐 Linux CPU 主機。本文件只準備移交，尚未連線或部署遠端；父端先盤點主機，決定路徑、可用 port、reverse proxy、部署身份及網路存取政策。不要與另一個 demo 同時部署。未購買雲資源、未改 IAM／防火牆。

## 交付物

- source tar.gz：由指定 Git commit 的 `git archive` 產生，只含追蹤程式、測試、Docker、README、授權及合法公開資料下載腳本。無 Git credentials、.env、虛擬環境、權重、客戶提案或錄影。
- public-samples tar.gz：只含 S001–S008 R01/R02 的三通道衍生 NPZ、原始 URL/SHA-256 manifest、評估數字及來源／授權告知。不是客戶資料；解壓到 source 根目錄，保留 data/ 子目錄。原始 EDF 不需搬遷，必要時以 `python -m scripts.prepare_data` 重建。
- 本機 artifacts/migration/manifest.json：源 commit、封包檔名、大小與 SHA-256。傳輸後先核對 SHA-256，再解壓。不要把 artifacts/ 或整個 Mac 工作區同步到遠端。

## 授權部署者的驗證順序

1. 在目標核對 `uname -m` 為 x86_64、Docker/Compose 已存在、可用 CPU/RAM/磁碟、現有容器與 port；不自行安裝或改安全設定。
2. 在確認的獨立部署目錄解壓 source，再解壓 public-samples。資料約 1 MB；安裝／建置另需映像空間。保留 `docs/SOURCES.md` 與 data/DATA_NOTICE.md。
3. 用現有 Docker 建置 Linux amd64，不搬運 Mac arm64 映像：

```sh
docker build --platform linux/amd64 -t og-eeg-demo:approved-commit .
docker compose config
# 確認映射 port 未衝突後，才由父端安排啟動
docker compose up -d
python3 scripts/verify_deployment.py --base-url http://127.0.0.1:8000
```

4. 驗證 container 為 non-root、CPU 2／RAM 2 GiB 上限、data 掛載唯讀、health 為 healthy。預設只綁 loopback，不是公開網址。
5. 瀏覽器驗收新版檢測報告：虛構個案、公開 S008 R01、13/15通過窗、四頻帶、原始片段定位、CSV錯誤恢復、PDF列印與JSON匯出。個案欄位不送分析API，CSV僅記憶體分析，不掛載上傳持久目錄。設備尚未串接。舊分類準確率不適用報告工作流。
6. 父端確認遠端驗收成功與持久化位置後，才另行授權 Mac 本案具名 container/image 清理。禁止全域 docker prune；保留原始碼及交付影片。任何新安裝、權限提示或存取拒絕先回報。

回復：在既定部署目錄切回先前已驗證 source commit/image，再 up；不得停止或覆寫其他專案容器。GitHub/GCP 工作流仍是未啟用的 preflight，不會因搬遷自動部署。

## Mac 資料可重建性

本案原驗證容器 `og-eeg-demo-local-check` 使用 `/Users/jeff.hong/Documents/Codex/2026-10-29/task/data` 唯讀 bind mount 到 `/app/data`，沒有 named volume。16 份 EDF 可由合法公開下載腳本重取；NPZ、manifest 和 evaluation 可重建。模型僅在記憶體訓練快取，無私有或不可重建權重。錄影與手動審閱輸出保留於 artifacts/，不是容器 volume，這次不清理。

## UI v2 交接注意

新版 source 已包含暖白／teal 單頁與完整 UI QA／錄影腳本，後端模型及 public-samples 內容不變。本輪依要求沒有操作 Mac Docker；既有具名映像是舊 UI，父端驗收後必須由新版 source 包重新 build，不能直接移交舊映像宣稱是新版。新截圖與無聲操作影片留在 artifacts/，未加入公開 source 包。
