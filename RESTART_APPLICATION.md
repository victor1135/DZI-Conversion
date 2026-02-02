# 重启应用以使用新的 libvips 8.18

## 问题

即使已经安装了 libvips 8.18（包含 JPEG2000 支持），应用仍然报错说缺少 JPEG2000 支持。

## 原因

应用在启动时已经加载了旧的 libvips 版本。Python 模块一旦导入，就会保持加载状态，即使更新了 PATH 环境变量也不会自动重新加载。

## 解决方案

### 步骤 1: 完全停止当前应用

1. 在运行应用的终端按 `Ctrl + C` 停止应用
2. 确保所有 Python 进程都已停止

### 步骤 2: 验证 libvips 8.18 路径

运行检查脚本确认：
```bash
python check_jpeg2000_support.py
```

应该看到：
- ✓ 找到 libvips: C:\vips-dev-8.18\bin
- ✓ 找到 libopenjp2.dll

### 步骤 3: 重新启动应用

```bash
# 激活虚拟环境（如果需要）
.\venv\Scripts\activate

# 启动应用
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 步骤 4: 检查启动日志

启动时应该看到：
```
[INFO] Found libvips with JPEG2000 support at: C:\vips-dev-8.18\bin
[OK] pyvips available - using libvips for high-performance conversion
[INFO] Application ready: pyvips is available for SVS conversion
```

### 步骤 5: 测试 SVS 文件

重新上传 SVS 文件，应该可以正常处理了。

## 如果仍然有问题

### 方法 1: 设置环境变量（推荐）

在启动应用前设置环境变量：

**PowerShell:**
```powershell
$env:VIPSHOME = "C:\vips-dev-8.18"
$env:PATH = "C:\vips-dev-8.18\bin;$env:PATH"
python -m uvicorn main:app --reload
```

**CMD:**
```cmd
set VIPSHOME=C:\vips-dev-8.18
set PATH=C:\vips-dev-8.18\bin;%PATH%
python -m uvicorn main:app --reload
```

### 方法 2: 创建 .env 文件

在项目根目录创建 `.env` 文件：
```
VIPSHOME=C:\vips-dev-8.18
```

然后重启应用。

### 方法 3: 系统环境变量（永久）

1. 按 `Win + R`，输入 `sysdm.cpl`
2. 高级 → 环境变量
3. 系统变量中：
   - 添加 `VIPSHOME` = `C:\vips-dev-8.18`
   - 或编辑 `Path`，添加 `C:\vips-dev-8.18\bin`（放在最前面）

然后重启终端和应用。

## 验证

运行测试脚本确认：
```bash
python test_svs_support.py
```

应该看到所有检查都通过。
