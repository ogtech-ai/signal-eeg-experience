# 驗證紀錄

環境：macOS arm64、Python 3.12.8、CPU；依賴完整鎖定於 requirements.lock。工作區為獨立新專案，父層與本工作區未找到 AGENTS.md；已查閱可用技能目錄，未找到適用的一般工程技能。這是實際多檔案程式專案，不採用靜態預覽／代建網站技能。

- API／數值測試：4 passed。涵蓋 alpha 頻譜差異、訓練／測試受試者隔離、獨立合成訊號預測、平坦／脈衝拒絕、完整 API、邊界及未知資料來源拒絕。
- Playwright Chromium：完整互動通過，含睜閉眼分類與場景幾何變化、人工雜訊拒絕、波形播放游標、JSON 下載、390px 手機溢出與 JS error 檢查。桌面／手機截圖在本機 artifacts/，已目視檢查。
- pip check：No broken requirements found。
- Docker：有 CLI，但 daemon 未啟動，故本機未完成 build/run。標準 CI 包含 docker build，尚待公司 repo 發布後實際執行。
- GitHub：公司連接器讀取身份確定為 ogtech-jeffhong；ogtech-ai/eeg-experience-demo 查詢回 404（不能保證不存在，也可能不可見），未覆寫任何 repo。可用工具缺少 create-repository；本機 gh 只有失效的 jeffhong824 與 homee-jeff-hong 登入，未採用。發布尚未完成，CI 尚無雲端執行結果。
- GCP：未提供 VM／身份，未遠端部署。部署 workflow 是明確 fail-closed 的手動 preflight 範本。

合成資料獨立受試者功能測試：180 訓練片段、60 測試片段，平衡準確率 100%，混淆矩陣 [[30,0],[0,30]]；此結果來自刻意可分離的人工訊號，**不能當作真實 EEG 表現**。

公開資料測試結果待下載完成後附於下方；完整逐檔 SHA-256 與 URL 留在本機 data/manifest.json，不把原始資料或模型權重放進 git。
