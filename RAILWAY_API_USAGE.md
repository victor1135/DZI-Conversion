# Railway 服務調用指南

## 1. 獲取服務 URL

在 Railway 項目頁面：
1. 點擊您的服務
2. 找到 **Settings** → **Networking**
3. 複製 **Public Domain**（例如：`your-app-name.up.railway.app`）
4. 完整 URL：`https://your-app-name.up.railway.app`

## 2. API 端點

### 2.1 健康檢查
```bash
curl https://your-app-name.up.railway.app/api/health
```

回應：
```json
{
  "status": "healthy"
}
```

### 2.2 查看服務信息
```bash
curl https://your-app-name.up.railway.app/
```

### 2.3 上傳檔案進行轉換

**使用 curl：**
```bash
curl -X POST https://your-app-name.up.railway.app/api/upload \
  -F "file=@/path/to/your/image.svs" \
  -F "provider=s3" \
  -F "bucket=2026-demo" \
  -F "region=eu-west-2"
```

**使用 Python：**
```python
import requests

url = "https://your-app-name.up.railway.app/api/upload"

with open("path/to/image.svs", "rb") as f:
    files = {"file": f}
    data = {
        "provider": "s3",
        "bucket": "2026-demo",
        "region": "eu-west-2"
    }
    response = requests.post(url, files=files, data=data)
    result = response.json()
    print(result)
    job_id = result["job_id"]
```

**使用 JavaScript/Node.js：**
```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const form = new FormData();
form.append('file', fs.createReadStream('path/to/image.svs'));
form.append('provider', 's3');
form.append('bucket', '2026-demo');
form.append('region', 'eu-west-2');

axios.post('https://your-app-name.up.railway.app/api/upload', form, {
  headers: form.getHeaders()
})
.then(response => {
  console.log(response.data);
  const jobId = response.data.job_id;
})
.catch(error => {
  console.error(error);
});
```

**回應範例：**
```json
{
  "job_id": "abc12345",
  "status": "pending",
  "message": "File uploaded successfully. Conversion started.",
  "status_url": "/api/status/abc12345"
}
```

### 2.4 查詢轉換狀態

**使用 curl：**
```bash
curl https://your-app-name.up.railway.app/api/status/abc12345
```

**使用 Python：**
```python
import requests
import time

job_id = "abc12345"
url = f"https://your-app-name.up.railway.app/api/status/{job_id}"

while True:
    response = requests.get(url)
    status = response.json()
    
    print(f"狀態: {status['status']}, 進度: {status['progress']}%")
    print(f"訊息: {status['message']}")
    
    if status['status'] == 'completed':
        print(f"DZI URL: {status['dzi_url']}")
        print(f"縮圖 URL: {status['thumbnail_url']}")
        break
    elif status['status'] == 'failed':
        print(f"轉換失敗: {status['message']}")
        break
    
    time.sleep(2)  # 每 2 秒查詢一次
```

**回應範例（進行中）：**
```json
{
  "job_id": "abc12345",
  "status": "converting",
  "progress": 45,
  "message": "Converting to DZI format...",
  "dzi_url": null,
  "thumbnail_url": null
}
```

**回應範例（完成）：**
```json
{
  "job_id": "abc12345",
  "status": "completed",
  "progress": 100,
  "message": "Conversion and upload completed successfully!",
  "dzi_url": "https://s3.amazonaws.com/bucket/dzi/abc12345/image.dzi",
  "thumbnail_url": "https://s3.amazonaws.com/bucket/dzi/abc12345/thumbnail.jpg"
}
```

### 2.5 列出所有任務

```bash
curl https://your-app-name.up.railway.app/api/jobs
```

## 3. 完整使用流程範例

### Python 完整範例
```python
import requests
import time

# 服務 URL
BASE_URL = "https://your-app-name.up.railway.app"

# 1. 上傳檔案
print("上傳檔案中...")
with open("path/to/image.svs", "rb") as f:
    files = {"file": f}
    data = {
        "provider": "s3",
        "bucket": "2026-demo",
        "region": "eu-west-2"
    }
    response = requests.post(f"{BASE_URL}/api/upload", files=files, data=data)
    result = response.json()
    job_id = result["job_id"]
    print(f"任務 ID: {job_id}")

# 2. 輪詢狀態
print("等待轉換完成...")
while True:
    response = requests.get(f"{BASE_URL}/api/status/{job_id}")
    status = response.json()
    
    print(f"[{status['progress']}%] {status['message']}")
    
    if status['status'] == 'completed':
        print(f"\n✅ 轉換完成！")
        print(f"DZI URL: {status['dzi_url']}")
        print(f"縮圖 URL: {status['thumbnail_url']}")
        break
    elif status['status'] == 'failed':
        print(f"\n❌ 轉換失敗: {status['message']}")
        break
    
    time.sleep(3)  # 每 3 秒查詢一次
```

### JavaScript/Node.js 完整範例
```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const BASE_URL = 'https://your-app-name.up.railway.app';

async function convertImage(filePath) {
  try {
    // 1. 上傳檔案
    console.log('上傳檔案中...');
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('provider', 's3');
    form.append('bucket', '2026-demo');
    form.append('region', 'eu-west-2');
    
    const uploadResponse = await axios.post(`${BASE_URL}/api/upload`, form, {
      headers: form.getHeaders()
    });
    
    const jobId = uploadResponse.data.job_id;
    console.log(`任務 ID: ${jobId}`);
    
    // 2. 輪詢狀態
    console.log('等待轉換完成...');
    while (true) {
      const statusResponse = await axios.get(`${BASE_URL}/api/status/${jobId}`);
      const status = statusResponse.data;
      
      console.log(`[${status.progress}%] ${status.message}`);
      
      if (status.status === 'completed') {
        console.log('\n✅ 轉換完成！');
        console.log(`DZI URL: ${status.dzi_url}`);
        console.log(`縮圖 URL: ${status.thumbnail_url}`);
        break;
      } else if (status.status === 'failed') {
        console.log(`\n❌ 轉換失敗: ${status.message}`);
        break;
      }
      
      await new Promise(resolve => setTimeout(resolve, 3000)); // 等待 3 秒
    }
  } catch (error) {
    console.error('錯誤:', error.message);
  }
}

// 使用範例
convertImage('path/to/image.svs');
```

## 4. 支援的檔案格式

- `.svs` (Aperio ScanScope)
- `.tiff` / `.tif` (TIFF)
- `.ndpi` (Hamamatsu)
- `.mrxs` (3DHistech)
- `.png` / `.jpg` / `.jpeg` (標準圖片格式)

## 5. 注意事項

1. **大檔案處理**：大檔案（>100MB）可能需要較長時間，請耐心等待
2. **環境變數**：確保在 Railway 中設置了必要的環境變數：
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_BUCKET`
   - `AWS_REGION`
   - 或 OSS 相關變數
3. **超時設定**：Railway 有請求超時限制，大檔案上傳可能需要調整設定
4. **CORS**：服務已配置 CORS，允許跨域請求

## 6. 錯誤處理

如果遇到錯誤，檢查：
- 服務是否正常運行（使用 `/api/health`）
- 檔案格式是否支援
- 環境變數是否正確設置
- Railway 日誌查看詳細錯誤信息
