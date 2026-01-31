# 上傳策略分析報告

## 📋 概述

本專案實現了一個高效的多階段上傳策略，用於處理病理切片圖像（Whole Slide Images）的轉換和雲端存儲。整個流程分為三個主要階段：文件接收、DZI 轉換、雲端上傳。

---

## 🔄 完整上傳流程

### 階段 1: 文件接收（`main.py` - `/api/upload`）

**流程：**
1. **文件驗證**：檢查文件擴展名（支援 `.svs`, `.tiff`, `.tif`, `.ndpi`, `.mrxs`, `.png`, `.jpg`, `.jpeg`）
2. **生成任務 ID**：使用 UUID 前 8 位作為唯一標識
3. **本地保存**：將上傳的文件保存到 `./uploads/{job_id}.{ext}`
4. **性能監控**：記錄上傳時間和速度
5. **異步處理**：使用 FastAPI 的 `BackgroundTasks` 啟動後台轉換任務

**關鍵特性：**
- ✅ 同步響應：立即返回 `job_id`，不阻塞用戶
- ✅ 進度追蹤：通過 `/api/status/{job_id}` 查詢進度
- ✅ 錯誤處理：文件保存失敗時返回 500 錯誤

---

### 階段 2: DZI 轉換（`dzi_converter.py`）

**流程：**
1. 使用 libvips 將原始圖像轉換為 DZI 金字塔格式
2. 生成多層級瓦片（tiles）和縮圖
3. 輸出到 `./output/{job_id}/` 目錄

**輸出結構：**
```
output/{job_id}/
├── {job_id}.dzi          # DZI 描述文件
├── {job_id}_thumbnail.jpg # 縮圖
└── {job_id}_files/        # 瓦片目錄
    ├── 0/                 # 層級 0（最低解析度）
    ├── 1/
    ├── ...
    └── 17/                 # 層級 17（最高解析度）
        ├── 0_0.jpg
        ├── 0_1.jpg
        └── ...
```

---

### 階段 3: 雲端上傳（`cloud_storage.py`）

這是**最核心的上傳策略**，包含多個優化技術。

---

## 🚀 核心上傳策略詳解

### 1. **雙存儲提供商支持**

#### AWS S3 (`S3Storage`)
- 支援 Public 和 Private Bucket
- Public Bucket 使用 `UNSIGNED` 簽名（無需 credentials）
- Private Bucket 需要 AWS Access Key 和 Secret Key

#### 阿里雲 OSS (`OSSStorage`)
- 使用 `oss2` SDK
- 需要 Access Key 和 Secret Key

---

### 2. **智能文件上傳策略**

#### 根據文件大小選擇上傳方法：

```python
# 小文件（< 5MB）：使用 put_object（更快，開銷更小）
if file_size < 5 * 1024 * 1024:
    shared_client.put_object(
        Bucket=self.bucket,
        Key=cloud_key,
        Body=f,
        ContentType=content_type
    )
# 大文件（≥ 5MB）：使用 upload_file with multipart
else:
    shared_client.upload_file(
        local_path,
        self.bucket,
        cloud_key,
        ExtraArgs={'ContentType': content_type},
        Config=transfer_config
    )
```

**優勢：**
- ✅ 小文件：`put_object` 減少 HTTP 請求開銷
- ✅ 大文件：`upload_file` 支援 multipart 上傳，提高可靠性

---

### 3. **動態並行度調整**

根據文件總數動態調整線程池大小：

```python
if total_files > 50000:
    max_workers = 100  # 超大量文件
elif total_files > 10000:
    max_workers = 50   # 大量文件
elif total_files > 1000:
    max_workers = 30   # 中等數量
else:
    max_workers = 20   # 少量文件
```

**設計理念：**
- 📊 文件越多，並行度越高
- ⚡ 充分利用 S3 的高並發能力
- 🎯 平衡網絡帶寬和系統資源

---

### 4. **優化的 boto3 配置**

```python
config = Config(
    connect_timeout=30,           # 連接超時
    read_timeout=60,              # 讀取超時
    retries={'max_attempts': 3, 'mode': 'adaptive'},  # 自適應重試
    max_pool_connections=100      # 連接池大小
)
```

**TransferConfig 設置：**
```python
transfer_config = boto3.s3.transfer.TransferConfig(
    multipart_threshold=1024 * 5,  # 5MB 以上使用 multipart
    max_concurrency=10,           # 並發上傳數
    multipart_chunksize=1024 * 5, # 每個分片 5MB
    use_threads=True,             # 使用多線程
    max_bandwidth=None            # 不限制帶寬
)
```

---

### 5. **並行上傳實現**

使用 `ThreadPoolExecutor` + `asyncio` 實現異步並行上傳：

```python
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    loop = asyncio.get_event_loop()
    futures = [
        loop.run_in_executor(executor, upload_file, args)
        for args in files_to_upload
    ]
    
    for future in asyncio.as_completed(futures):
        result = await future
        # 處理結果和進度更新
```

**優勢：**
- ✅ 非阻塞：使用 `asyncio.as_completed` 處理完成的上傳
- ✅ 進度追蹤：實時更新上傳進度
- ✅ 錯誤處理：記錄失敗的上傳，最後統一報告

---

### 6. **文件組織策略**

**雲端路徑結構：**
```
dzi/{job_id}/{base_name}.dzi
dzi/{job_id}/{base_name}_thumbnail.jpg
dzi/{job_id}/{base_name}_files/{level}/{tile_x}_{tile_y}.jpg
```

**特點：**
- 📁 按任務 ID 組織，避免衝突
- 🗂️ 清晰的目錄結構，易於管理
- 🔗 生成可直接訪問的 URL

---

### 7. **進度監控和性能分析**

#### 實時進度報告：
- 每上傳 100 個文件輸出一次進度
- 顯示：進度百分比、上傳速度（MB/s）、預計剩餘時間（ETA）

#### 性能指標：
```
[PERF] Upload stage started:
  Total files: 8545
  Total size: 245.67 MB
  Average file size: 29.45 KB

[PERF] Upload stage completed:
  Time: 720.45s (12.01 min)
  Speed: 0.34 MB/s
  Throughput: 11.9 files/sec
  Total uploaded: 245.67 MB (8545 files)
```

---

### 8. **錯誤處理和重試機制**

- ✅ **自動重試**：boto3 配置了 3 次自適應重試
- ✅ **失敗追蹤**：記錄所有失敗的上傳
- ✅ **詳細錯誤報告**：顯示前 10 個失敗的文件
- ✅ **異常拋出**：如果有失敗，拋出異常中斷流程

---

## 📊 性能優化亮點

### 1. **共享 boto3 Client**
```python
shared_client = boto3.client('s3', ...)  # 線程安全，可重用
```
- 避免為每個文件創建新的 client
- 減少連接開銷

### 2. **文件預處理**
- 提前收集所有需要上傳的文件
- 計算總大小，用於性能分析
- 按層級和文件名排序，確保順序

### 3. **層級驗證**
```python
# 檢查是否有缺失的層級
expected_levels = set(range(min(levels_found), max(levels_found) + 1))
actual_levels = set(levels_found)
missing_levels = expected_levels - actual_levels
```
- 確保 DZI 結構完整性
- 避免 OpenSeadragon 查看器出錯

---

## 🔍 潛在優化點

### 1. **斷點續傳**
- 當前實現：失敗後需要重新上傳所有文件
- 優化建議：記錄已上傳的文件，支持斷點續傳

### 2. **批量操作**
- 當前實現：每個文件單獨上傳
- 優化建議：對於小文件，可以使用 S3 的批量操作 API

### 3. **壓縮優化**
- 當前實現：直接上傳 JPEG/PNG 瓦片
- 優化建議：可以考慮使用 WebP 格式減少文件大小

### 4. **CDN 集成**
- 當前實現：直接從 S3 提供文件
- 優化建議：集成 CloudFront 或類似 CDN 加速訪問

---

## 📈 預期性能表現

根據代碼配置和策略：

| 文件數量 | 並行度 | 預期吞吐量 |
|---------|--------|-----------|
| < 1,000 | 20 workers | ~10-15 files/sec |
| 1,000 - 10,000 | 30 workers | ~15-25 files/sec |
| 10,000 - 50,000 | 50 workers | ~20-30 files/sec |
| > 50,000 | 100 workers | ~25-40 files/sec |

**實際性能取決於：**
- 網絡帶寬
- S3 區域和連接質量
- 文件大小分佈
- 系統資源（CPU、內存）

---

## 🎯 總結

本專案的上傳策略具有以下優勢：

1. ✅ **高效並行**：動態調整並行度，充分利用雲存儲的高並發能力
2. ✅ **智能選擇**：根據文件大小選擇最優上傳方法
3. ✅ **可靠穩定**：自動重試、錯誤追蹤、詳細日誌
4. ✅ **用戶友好**：實時進度、性能監控、清晰錯誤信息
5. ✅ **可擴展性**：支持多種雲存儲提供商，易於擴展

這是一個**生產級別**的上傳策略實現，適合處理大量小文件的場景（如 DZI 瓦片）。
