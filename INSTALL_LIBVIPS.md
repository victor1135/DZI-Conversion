# Windows 安裝 libvips 指南

## 步驟 1: 下載 libvips

1. 前往 [libvips GitHub Releases](https://github.com/libvips/libvips/releases)
2. 下載最新版本的 `vips-dev-w64-web-*.zip`（例如：`vips-dev-w64-web-8.15.0.zip`）
3. 解壓縮到一個固定位置，例如：
   - `C:\vips-dev-8.15.0\`
   - 或 `D:\libs\vips-dev-8.15.0\`

## 步驟 2: 設置環境變量

### 方法 A: 系統環境變量（推薦）

1. 按 `Win + R`，輸入 `sysdm.cpl`，按 Enter
2. 點擊「進階」標籤 → 「環境變數」
3. 在「系統變數」中找到 `Path`，點擊「編輯」
4. 點擊「新增」，添加 libvips 的 `bin` 目錄路徑，例如：
   ```
   C:\vips-dev-8.15.0\bin
   ```
5. 點擊「確定」保存所有對話框
6. **重新啟動命令提示字元或 PowerShell**（讓環境變數生效）

### 方法 B: 在代碼中設置（臨時）

在 `dzi_converter.py` 開頭添加：

```python
import os
# 設置 libvips 路徑（根據你的實際安裝路徑修改）
vipshome = r'C:\vips-dev-8.15.0\bin'
os.environ['PATH'] = vipshome + ';' + os.environ['PATH']
```

## 步驟 3: 驗證安裝

在 PowerShell 或命令提示字元中執行：

```bash
python -c "import pyvips; print('libvips version:', pyvips.version(0)); img = pyvips.Image.black(1, 1); print('Success!')"
```

如果看到版本號和 "Success!"，表示安裝成功！

## 步驟 4: 測試 SVS 轉換

現在您可以上傳 `.svs` 檔案進行轉換了！

## 常見問題

### Q: 仍然出現 "cannot load library 'libvips-42.dll'" 錯誤
A: 
- 確認環境變數已正確設置
- 確認 `bin` 目錄中有 `libvips-42.dll` 檔案
- 重新啟動終端機或 IDE
- 檢查路徑中沒有中文字元或特殊符號

### Q: 如何確認 libvips 路徑是否正確？
A: 在 PowerShell 中執行：
```powershell
Get-ChildItem -Path "C:\vips-dev-8.15.0\bin" -Filter "libvips-*.dll"
```
應該能看到 `libvips-42.dll` 或類似檔案。

## 其他平台

### macOS
```bash
brew install vips
pip install pyvips
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install libvips-dev
pip install pyvips
```

### Linux (CentOS/RHEL)
```bash
sudo yum install vips-devel
pip install pyvips
```
