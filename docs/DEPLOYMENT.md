> 最新選定搬遷目標是常駐 已指定的常駐 Linux CPU 主機，尚未遠端部署；目前移交依 [MIGRATION.md](MIGRATION.md)。下方 GCP 設定保留為未啟用範本，不是本次部署指令。

# GCP CPU VM 部署交接

狀態：等待使用者提供既有 VM；未購買資源、未部署、未改 IAM／防火牆。維持 GCP VM 路徑，不使用 Cloud Run。

最小缺項：GCP Project ID、VM 名稱、zone、CPU/RAM/OS/架構、部署身份及允許的登入方式、網域／HTTPS 與存取範圍。也需確認 VM 已有 Docker Compose、repo 取得方式與部署目錄。

準備完成後，由獲授權管理者先設定 GitHub environment `demo` 與 required reviewers。可評估 Workload Identity Federation + 短效身份，限定公司 repo、branch 和 environment；不能自行套用持久 IAM。`GCP_PROJECT_ID`、`GCP_VM_NAME`、`GCP_ZONE`、`GCP_WIF_PROVIDER`、`GCP_SERVICE_ACCOUNT` 僅為預備變數。本版 workflow 故意只檢查設定並退出失敗，不含遠端步驟或 id-token 權限。

未來授權完成後，部署 workflow 應檢查測試、固定 commit、建立映像、傳輸到指定 VM、在指定目錄啟動 compose、檢查 loopback health；記錄前一映像供回復。不要將工作目錄任意內容同步到 VM。不要建立或輸出長效金鑰。

VM 手動驗證指令（由已授權且在正確主機的管理者執行）：

```sh
docker compose build
docker compose up -d
curl --fail http://127.0.0.1:8000/api/health
docker compose logs --tail=50
```

此 compose 只綁 loopback。公開網址需另由管理者配置 HTTPS、存取政策與網域；本機網址不是客戶可用部署。回復時切回前一已驗證 commit 並重新 build/up。公開資料放於 VM 的 data 目錄，不進 git，也不放 Actions artifact。
