# 報告工作流驗收（0.2）

此次更新以檢測報告取代湖面體驗作主要情境。原視覺版有本機回退標籤 `experience-ui-reviewed-9c8f6cb`。此文件與 README 為最新情境；UI_REDESIGN.md / VALIDATION.md 記錄舊版本。

- Mac CPU：23 項 pytest 通過（上游 Starlette/httpx 一項 deprecation warning），ruff 與 JavaScript 語法檢查通過。
- Chromium 實際 UI：1440/1280/390/360px 無水平溢位；匿名虛構個案、公開／合成、真 CSV 上傳、格式錯誤／NaN 拒絕及恢復、遮罩定位、下載原值、JSON 匯出、清空、列印連接、無 JavaScript 錯誤。
- 隱私檢查：具辨識性的 QA 匿名代號未出現在任何請求 URL/body，瀏覽器無 localStorage/sessionStorage；API無檔案持久化；報告回應 no-store。
- 公開 S008 R01：61秒，160Hz，O1/Oz/O2。15完整四秒窗，13窗／52秒納入平均；2窗Q1排除；1秒尾段保留不評分。可重現四頻帶，不代表品質或醫療模型的整體準確率。
- 合成純10Hz/6Hz輸入用獨立數值斷言驗證頻帶；合成偽跡能觸發 Q1/Q2/A1/A2；眼睛條件不改變品質遮罩；全拒絕時沒有頻帶或平均PSD。
- PDF：使用同一列印CSS生成 A4三頁，實看確認頻帶、波形、PSD、時間頻率、觀察、完整遮罩、規則及來源可讀，無空白尾頁。輸出只留忽略的 output/pdf/。
- 無聲影片：Playwright只錄應用 viewport；實際公開睜閉眼、合成拒噪、公開CSV下載後重新上傳、定位、報告、JSON匯出與列印。以 ffmpeg 轉 MP4、ffprobe 驗證僅 video stream、完整解碼驗證。

限制：上傳僅CSV，不支援EDF；A1/A2為未驗證啟發式；沒有疾病／心理狀態模型、年齡常模或現場設備串接。沒有重做Docker runtime驗收（既有Mac容器保持原狀）；Linux amd64需由授權部署者以新commit重建並執行 scripts/verify_deployment.py。此次未部署或變更公開路由。
