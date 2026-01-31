# SVS 檔案轉換快速設置指南

## 問題
上傳 SVS 檔案時出現錯誤：
```
檔案格式 .svs 需要 pyvips (libvips) 才能處理
```

## 解決方案

### 步驟 1: 下載 libvips

1. 前往：https://github.com/libvips/libvips/releases
2. 下載最新版本的 `vips-dev-w64-web-*.zip`（例如：`vips-dev-w64-web-8.15.0.zip`）
3. 解壓縮到固定位置，例如：`C:\vips-dev-8.15.0\`

### 步驟 2: 設置路徑（三選一）

#### 方法 A: 使用環境變數（推薦）

1. 在專案根目錄創建 `.env` 檔案（如果還沒有）
2. 添加以下內容：
   ```
   VIPSHOME=C:\vips-dev-8.15.0
   ```
   （根據你的實際解壓縮路徑修改）

3. 重新啟動應用程式

#### 方法 B: 系統環境變數（永久設置）

1. 按 `Win + R`，輸入 `sysdm.cpl`
2. 點擊「進階」→「環境變數」
3. 在「系統變數」中：
   - 新增 `VIPSHOME` = `C:\vips-dev-8.15.0`
   - 或編輯 `Path`，新增 `C:\vips-dev-8.15.0\bin`
4. 重新啟動終端機和應用程式

#### 方法 C: 在代碼中設置（臨時）

在 `dzi_converter.py` 開頭（第 9 行附近）添加：

```python
import os
# 設置 libvips 路徑
vipshome = r'C:\vips-dev-8.15.0'
os.environ['VIPSHOME'] = vipshome
os.environ['PATH'] = os.path.join(vipshome, 'bin') + ';' + os.environ['PATH']
```

### 步驟 3: 驗證安裝

運行測試腳本：
```bash
python setup_libvips_path.py
```

或直接測試：
```bash
python -c "import pyvips; print('Success! Version:', pyvips.version(0))"
```

### 步驟 4: 重新上傳 SVS 檔案

設置完成後，重新啟動應用程式，然後再次上傳 SVS 檔案。

## 自動搜尋功能

系統會自動在以下位置搜尋 libvips：
- `C:\vips-dev-8.15.0\bin`
- `C:\vips-dev-8.14.0\bin`
- `C:\vips-dev-8.13.0\bin`
- `D:\vips-dev-8.15.0\bin`

如果 libvips 安裝在這些位置，系統會自動找到並使用。

## 其他平台

### macOS
```bash
brew install vips
pip install pyvips
```

### Linux
```bash
sudo apt-get install libvips-dev
pip install pyvips
```

## 需要幫助？

查看詳細說明：`INSTALL_LIBVIPS.md`
