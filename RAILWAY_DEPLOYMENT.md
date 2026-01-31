# Railway 部署指南

## 📋 概述

Railway 運行在 **Linux 容器**中，不是 Windows。本指南說明如何正確部署此專案到 Railway。

---

## ✅ Railway 自動識別環境

Railway **會自動識別** Linux 環境並：
- 使用正確的包管理器（apt-get/yum/apk）
- 執行正確的命令
- 設置正確的環境變數

**你不需要手動區分平台！** Railway 會自動處理。

---

## 🚀 部署步驟

### 方法 1: 使用 Dockerfile（推薦）

Railway 會自動檢測 `Dockerfile` 並使用它來構建和部署。

**優點：**
- ✅ 環境一致性最好
- ✅ 自動安裝 libvips
- ✅ 可預測的構建過程

**步驟：**
1. 確保 `Dockerfile` 存在於項目根目錄
2. 將代碼推送到 GitHub
3. 在 Railway 中連接 GitHub 倉庫
4. Railway 會自動檢測 Dockerfile 並部署

---

### 方法 2: 使用 Nixpacks（自動檢測）

如果沒有 Dockerfile，Railway 會使用 Nixpacks 自動檢測項目類型。

**步驟：**
1. 確保 `requirements.txt` 存在
2. 確保 `railway.json` 存在（可選，用於自定義配置）
3. 將代碼推送到 GitHub
4. Railway 會自動：
   - 檢測到 Python 項目
   - 安裝系統依賴（包括 libvips）
   - 安裝 Python 依賴
   - 啟動應用

---

## 🔧 環境變數設置

在 Railway 項目設置中添加以下環境變數：

### AWS S3（如果使用）
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_BUCKET=your_bucket_name
AWS_REGION=eu-west-2
S3_PUBLIC=true
```

### 阿里雲 OSS（如果使用）
```
OSS_ACCESS_KEY_ID=your_access_key
OSS_ACCESS_KEY_SECRET=your_secret_key
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

### 應用配置
```
HOST=0.0.0.0
PORT=8000  # Railway 會自動設置，通常不需要手動設置
```

---

## 📦 libvips 安裝

### 自動安裝（推薦）

**使用 Dockerfile：**
```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libvips-dev \
    && rm -rf /var/lib/apt/lists/*
```

**使用 Nixpacks：**
Railway 會自動檢測並安裝系統依賴。如果沒有自動安裝，可以在 `railway.json` 中添加：

```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "apt-get update && apt-get install -y libvips-dev && pip install -r requirements.txt"
  }
}
```

### 驗證安裝

應用啟動時會自動檢查 libvips 是否可用：
```
[OK] pyvips available - using libvips for high-performance conversion
```

如果看到：
```
[INFO] pyvips not available
```
表示 libvips 未正確安裝，但應用仍可使用 Pillow 處理基本圖片格式（不支持 SVS）。

---

## 🐛 常見問題

### Q: Railway 會自動安裝 libvips 嗎？

**A:** 
- 如果使用 Dockerfile：**是**，會自動安裝
- 如果使用 Nixpacks：**可能**，取決於自動檢測。建議使用 Dockerfile 確保安裝

### Q: 如何確認 Railway 運行在 Linux 環境？

**A:** Railway 始終運行在 Linux 容器中。你可以在 Railway 的日誌中看到：
```
Detected OS: Linux
```

### Q: 代碼中的 Windows 路徑會影響 Linux 部署嗎？

**A:** **不會**。代碼已經更新為跨平台：
- 自動檢測操作系統
- Windows 使用 `;` 作為路徑分隔符
- Linux 使用 `:` 作為路徑分隔符
- Linux 上 libvips 通常安裝在系統路徑，pyvips 會自動找到

### Q: 如何查看部署日誌？

**A:** 在 Railway 控制台：
1. 點擊你的服務
2. 查看 "Deployments" 標籤
3. 點擊最新的部署查看日誌

### Q: 啟動失敗怎麼辦？

**A:** 檢查以下幾點：
1. **環境變數**：確保 AWS/OSS 憑證已設置
2. **端口**：確保使用 `$PORT` 環境變數（Railway 自動提供）
3. **依賴**：檢查 `requirements.txt` 是否完整
4. **日誌**：查看 Railway 部署日誌中的錯誤信息

---

## 📝 部署檢查清單

- [ ] 代碼已推送到 GitHub
- [ ] `Dockerfile` 或 `railway.json` 存在
- [ ] `requirements.txt` 包含所有依賴
- [ ] 環境變數已在 Railway 中設置
- [ ] 測試本地構建（可選）：`docker build -t test .`
- [ ] 檢查部署日誌確認 libvips 已安裝
- [ ] 測試 API 端點是否正常響應

---

## 🔗 相關文件

- `Dockerfile` - Docker 構建配置
- `railway.json` - Railway 配置（可選）
- `setup.sh` - 部署腳本（可選）
- `requirements.txt` - Python 依賴

---

## 💡 最佳實踐

1. **使用 Dockerfile**：確保環境一致性
2. **設置環境變數**：不要在代碼中硬編碼憑證
3. **監控日誌**：部署後檢查啟動日誌
4. **測試端點**：部署後測試 `/api/health` 端點
5. **版本控制**：使用 Git 標籤管理版本

---

## 🎯 總結

**Railway 會自動識別 Linux 環境**，你不需要手動區分平台。只需：
1. 確保 `Dockerfile` 存在（推薦）
2. 設置環境變數
3. 推送到 GitHub
4. Railway 會處理其餘部分！

如有問題，查看 Railway 部署日誌獲取詳細錯誤信息。
