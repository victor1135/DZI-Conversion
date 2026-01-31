# 性能監控說明

## 概述

系統現在包含詳細的性能監控功能，可以幫助診斷哪個階段是瓶頸。

## 監控的階段

### 1. 📤 文件上傳階段
**位置：** `main.py` - `/api/upload` 端點

**監控指標：**
- 文件大小（MB）
- 上傳時間（秒）
- 上傳速度（MB/s）

**輸出示例：**
```
[PERF] File upload: 800.45 MB in 65.23s (12.27 MB/s)
```

---

### 2. 🔄 DZI 轉換階段
**位置：** `dzi_converter.py` - `_convert_with_vips()` 方法

**監控指標：**
- 輸入文件大小（MB）
- 圖像尺寸（寬x高）
- 圖像載入時間
- dzsave 處理時間
- 總轉換時間
- 處理速度（MB/s）
- 生成的層級數和瓦片數
- 輸出文件大小（DZI + 瓦片）

**輸出示例：**
```
[PERF] Starting DZI conversion:
  Input file: slide.svs (800.45 MB)
  Image size: 195000x130000 pixels
  Image load time: 2.34s
[PERF] DZI conversion completed:
  Total time: 1250.67s (20.84 min)
  - Image load: 2.34s
  - dzsave: 1248.33s (99.8%)
  Processing speed: 0.64 MB/s
  Generated: 9 levels, 8543 tiles
  Output size: 245.67 MB (DZI: 0.01 MB, Tiles: 245.66 MB)
```

---

### 3. ☁️ 上傳到 S3 階段
**位置：** `cloud_storage.py` - `upload_dzi()` 方法

**監控指標：**
- 總文件數
- 總數據大小（MB）
- 平均文件大小（KB）
- 上傳時間
- 上傳速度（MB/s）
- 吞吐量（files/sec）
- 實時進度（每 100 個文件）

**輸出示例：**
```
[PERF] Upload stage started:
  Total files: 8545
  Total size: 245.67 MB
  Average file size: 29.45 KB
[INFO] Upload progress: 100/8545 (1%) | Speed: 2.34 MB/s | ETA: 15.2 min
[INFO] Upload progress: 200/8545 (2%) | Speed: 2.45 MB/s | ETA: 14.8 min
...
[PERF] Upload stage completed:
  Time: 720.45s (12.01 min)
  Speed: 0.34 MB/s
  Throughput: 11.9 files/sec
  Total uploaded: 245.67 MB (8545 files)
```

---

### 4. 📊 整體流程監控
**位置：** `main.py` - `process_conversion()` 函數

**監控指標：**
- 總處理時間
- 各階段時間分配（百分比）
- CPU 使用率（需要 psutil）
- 內存使用情況（需要 psutil）

**輸出示例：**
```
============================================================
[PERF] Job c420c759 started
[PERF] Input file: slide.svs (800.45 MB)
[PERF] Initial CPU: 5.2%, Memory: 125.34 MB
============================================================

[PERF] Conversion stage completed:
  Time: 1250.67s (20.84 min)
  Speed: 0.64 MB/s
  Output size: 245.67 MB (DZI: 0.01 MB, Tiles: 245.66 MB)
  CPU usage: 5.2% -> 85.3%
  Memory usage: 125.34 MB -> 512.45 MB (+387.11 MB)

[PERF] Upload stage completed:
  Time: 720.45s (12.01 min)
  Speed: 0.34 MB/s
  Data uploaded: 245.67 MB
  Memory usage: 512.45 MB -> 498.23 MB

============================================================
[PERF] Job c420c759 completed successfully
[PERF] Total time: 1971.12s (32.85 min)
[PERF] Time breakdown:
  - Conversion: 1250.67s (63.5%)
  - Upload: 720.45s (36.5%)
  - Other: 0.00s
[PERF] Final CPU: 8.5%, Memory: 498.23 MB
============================================================
```

---

## 安裝性能監控依賴

### 基本監控（無需額外依賴）
基本時間和文件大小監控已經內建，無需額外安裝。

### 完整監控（推薦）
安裝 `psutil` 以獲得 CPU 和內存使用情況：

```bash
pip install psutil
```

或使用 requirements.txt：
```bash
pip install -r requirements.txt
```

---

## 如何診斷瓶頸

### 1. 查看時間分配
查看整體流程監控的最後輸出，看哪個階段佔用時間最多：
- **轉換階段 > 60%** → CPU 或磁盤 I/O 瓶頸
- **上傳階段 > 40%** → 網絡帶寬瓶頸

### 2. 查看處理速度
- **轉換速度 < 1 MB/s** → 可能是 CPU 或磁盤慢
- **上傳速度 < 0.5 MB/s** → 網絡帶寬不足

### 3. 查看 CPU 使用率
- **CPU < 50%** → 可能是磁盤 I/O 瓶頸（使用 SSD 會改善）
- **CPU > 90%** → CPU 是瓶頸（已充分利用）

### 4. 查看內存使用
- **內存持續增長** → 可能有內存洩漏
- **內存使用過高** → 可能需要增加系統內存

---

## 優化建議

根據監控結果：

### 如果轉換階段慢（CPU < 50%）
1. 使用 SSD 存儲（可以提升 50-70%）
2. 檢查磁盤 I/O 使用率

### 如果轉換階段慢（CPU > 90%）
1. 已經充分利用 CPU
2. 考慮使用更快的 CPU
3. 檢查 libvips 線程配置

### 如果上傳階段慢
1. 增加網絡帶寬
2. 考慮使用 S3 Transfer Acceleration
3. 檢查網絡延遲

---

## 日誌位置

所有性能監控輸出都會寫入：
- **控制台輸出**（如果使用 uvicorn 運行）
- **應用程序日誌**（如果配置了日誌系統）

---

## 注意事項

1. **psutil 是可選的**：如果未安裝，CPU 和內存監控會顯示 0，但時間監控仍然有效
2. **性能監控有輕微開銷**：通常 < 1%，可以忽略
3. **實時進度更新**：上傳階段每 100 個文件更新一次，避免過多輸出
