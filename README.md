# Oxford Pathology - DZI Conversion Backend

將病理切片轉換為 Deep Zoom Image (DZI) 格式的 Python 後端服務。

## 功能

- 📤 接收上傳的病理切片檔案 (.svs, .tiff, .ndpi, .mrxs, .png, .jpg)
- 🔄 轉換為 DZI 金字塔瓦片格式
- ☁️ 上傳到 AWS S3 或阿里雲 OSS
- 📊 即時進度追蹤

## 安裝

### 1. 安裝 libvips (推薦，處理大檔案更快)

**Windows:**
```bash
# 使用 chocolatey
choco install libvips

# 或下載預編譯版本
# https://github.com/libvips/libvips/releases
```

**macOS:**
```bash
brew install vips
```

**Ubuntu/Debian:**
```bash
sudo apt-get install libvips-dev
```

### 2. 安裝 Python 依賴

```bash
cd demo/backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env 填入你的 S3/OSS 配置
```

## 執行

```bash
# 開發模式
python main.py

# 或使用 uvicorn
uvicorn main:app --reload --port 8000
```

服務啟動在 http://localhost:8000

## API 端點

### 上傳檔案
```http
POST /api/upload
Content-Type: multipart/form-data

file: <檔案>
provider: s3 (或 oss)
bucket: 2026-demo
region: eu-west-2
```

回應：
```json
{
  "job_id": "abc12345",
  "status": "pending",
  "message": "File uploaded successfully. Conversion started.",
  "status_url": "/api/status/abc12345"
}
```

### 查詢狀態
```http
GET /api/status/{job_id}
```

回應：
```json
{
  "job_id": "abc12345",
  "status": "completed",
  "progress": 100,
  "message": "Conversion and upload completed successfully!",
  "dzi_url": "https://2026-demo.s3.eu-west-2.amazonaws.com/dzi/abc12345/slide.dzi",
  "thumbnail_url": "https://2026-demo.s3.eu-west-2.amazonaws.com/dzi/abc12345/slide_thumbnail.jpg"
}
```

## 前端整合

```typescript
// 上傳檔案
const formData = new FormData()
formData.append('file', file)
formData.append('provider', 's3')
formData.append('bucket', '2026-demo')
formData.append('region', 'eu-west-2')

const response = await fetch('http://localhost:8000/api/upload', {
  method: 'POST',
  body: formData
})
const { job_id } = await response.json()

// 輪詢狀態
const checkStatus = async () => {
  const res = await fetch(`http://localhost:8000/api/status/${job_id}`)
  const status = await res.json()
  
  if (status.status === 'completed') {
    console.log('DZI URL:', status.dzi_url)
    // 可以用 OpenSeadragon 載入這個 DZI
  } else if (status.status === 'failed') {
    console.error('Conversion failed:', status.message)
  } else {
    // 繼續等待
    setTimeout(checkStatus, 1000)
  }
}
checkStatus()
```

## 目錄結構

```
backend/
├── main.py              # FastAPI 主程式
├── dzi_converter.py     # DZI 轉換邏輯
├── cloud_storage.py     # S3/OSS 上傳
├── requirements.txt     # Python 依賴
├── .env.example         # 環境變數範例
└── README.md
```

## DZI 格式說明

Deep Zoom Image (DZI) 是微軟開發的金字塔式圖片格式：

```
slide/
├── slide.dzi           # XML 描述檔
└── slide_files/
    ├── 0/              # 最小層級 (1x1 px)
    │   └── 0_0.jpg
    ├── 1/
    ├── ...
    └── 18/             # 最大層級 (原始大小)
        ├── 0_0.jpg     # 256x256 瓦片
        ├── 0_1.jpg
        └── ...
```

這種格式讓瀏覽器可以只載入可見區域的瓦片，而不需要下載整個大檔案。

## 🚀 部署到 Railway

### 快速部署

1. **推送到 GitHub**
   ```bash
   git add .
   git commit -m "Ready for Railway deployment"
   git push origin main
   ```

2. **在 Railway 中連接倉庫**
   - 登入 [Railway](https://railway.app)
   - 點擊 "New Project" → "Deploy from GitHub repo"
   - 選擇你的倉庫

3. **設置環境變數**
   在 Railway 項目設置中添加：
   ```
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   AWS_BUCKET=your_bucket
   AWS_REGION=eu-west-2
   ```

4. **部署完成！**
   Railway 會自動：
   - ✅ 檢測到 Dockerfile
   - ✅ 安裝 libvips（Linux 環境）
   - ✅ 安裝 Python 依賴
   - ✅ 啟動應用

### 重要說明

- **Railway 運行在 Linux 容器中**，不是 Windows
- **代碼已自動處理跨平台**：Windows 和 Linux 都能正常工作
- **libvips 會自動安裝**：Dockerfile 中已包含安裝步驟
- **無需手動區分平台**：Railway 會自動識別環境

詳細部署指南請參考：[RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md)

