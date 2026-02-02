# Windows 本地环境 JPEG2000 支持修复指南

## 🔍 检查结果

根据检查，您的系统：
- ✅ libvips 已安装：`C:\vips-dev-8.15.0\`
- ✅ libvips 版本：8.18.0
- ✅ pyvips 可以正常加载
- ❌ **缺少 JPEG2000 支持**（未找到 openjpeg DLL）

## 🎯 问题原因

当前安装的 libvips 版本（可能是 `vips-dev-w64-*.zip` 基础版本）不包含 JPEG2000 支持。

SVS 文件内部使用 JPEG2000 压缩，需要包含 openjpeg 库的 libvips 版本。

## ✅ 解决方案

### 步骤 1: 下载包含 JPEG2000 支持的版本

1. 前往：https://github.com/libvips/libvips/releases
2. **下载 `vips-dev-w64-all-8.18.0.zip`**（或最新版本）
   - ⭐ **必须下载 `-all-` 版本**（包含所有格式支持）
   - ❌ 不要使用 `vips-dev-w64-8.18.0.zip`（基础版本，不包含 JPEG2000）

### 步骤 2: 替换安装

1. **备份当前安装**（可选）：
   ```powershell
   Rename-Item "C:\vips-dev-8.15.0" "C:\vips-dev-8.15.0-backup"
   ```

2. **解压新版本**：
   - 解压 `vips-dev-w64-all-8.18.0.zip` 到 `C:\vips-dev-8.18.0\`
   - 或者直接解压到 `C:\vips-dev-8.15.0\`（覆盖）

3. **验证安装**：
   ```powershell
   # 检查是否有 openjpeg DLL
   Get-ChildItem "C:\vips-dev-8.18.0\bin" -Filter "*openjp*.dll"
   # 应该看到 libopenjp2.dll 或 openjpeg.dll
   ```

### 步骤 3: 更新代码（如果需要）

如果解压到新路径（如 `C:\vips-dev-8.18.0\`），需要更新 `dzi_converter.py` 中的路径：

```python
# 在 dzi_converter.py 的 _try_find_libvips() 函数中
common_paths = [
    r"C:\vips-dev-8.18.0\bin",  # 新版本
    r"C:\vips-dev-8.15.0\bin",  # 旧版本
    # ...
]
```

### 步骤 4: 验证修复

运行检查脚本：
```bash
python check_jpeg2000_support.py
```

应该看到：
- ✓ 找到 libvips
- ✓ 找到 openjpeg DLL
- ✓ JPEG2000 支持可用

### 步骤 5: 测试 SVS 文件

重新运行应用并上传 SVS 文件，应该可以正常处理了。

## 📋 快速检查清单

- [ ] 下载了 `vips-dev-w64-all-*.zip`（不是基础版本）
- [ ] 解压到 `C:\vips-dev-8.18.0\` 或覆盖 `C:\vips-dev-8.15.0\`
- [ ] 检查 `bin` 目录中有 `libopenjp2.dll` 或 `openjpeg.dll`
- [ ] 运行 `python check_jpeg2000_support.py` 验证
- [ ] 重新启动应用测试 SVS 文件

## 🔗 下载链接

直接下载链接（请检查最新版本）：
- https://github.com/libvips/libvips/releases/download/v8.18.0/vips-dev-w64-all-8.18.0.zip

## 💡 提示

如果下载速度慢，可以：
1. 使用镜像站点
2. 或使用下载工具（如 IDM、迅雷等）

下载完成后，按照上面的步骤操作即可。
