# libvips JPEG2000 支持修复指南

## 问题

上传 SVS 文件时出现错误：
```
jp2k: libvips built without JPEG2000 support
tiff2vips: decompress error tile 0 x 0
```

## 原因

SVS 文件内部使用 **JPEG2000** 压缩格式，但 libvips 在编译时没有包含 JPEG2000 支持。

## 解决方案

### Railway 部署（Dockerfile）

已更新 `Dockerfile`，添加了 `libopenjp2-7-dev` 和 `libopenjp2-tools`：

```dockerfile
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    python3-dev \
    libvips-dev \
    libopenjp2-7-dev \      # JPEG2000 支持（开发库）
    libopenjp2-tools \      # JPEG2000 工具
    pkg-config \
    && rm -rf /var/lib/apt/lists/*
```

### 本地开发（Windows）

#### 方法 1：使用预编译版本（推荐）

1. 下载包含 JPEG2000 支持的 libvips：
   - 前往：https://github.com/libvips/libvips/releases
   - 下载 **`vips-dev-w64-web-*.zip`**（web 版本包含更多格式支持）
   - 或下载 **`vips-dev-w64-all-*.zip`**（包含所有格式支持）

2. 解压并设置环境变量（参考 `INSTALL_LIBVIPS.md`）

#### 方法 2：从源码编译（高级）

如果需要从源码编译 libvips 并包含 JPEG2000 支持：

```bash
# 安装依赖
# Windows (使用 vcpkg 或 MSYS2)
pacman -S openjpeg

# 然后编译 libvips
# 参考：https://github.com/libvips/libvips/blob/master/README.md
```

### 本地开发（Linux/macOS）

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    libvips-dev \
    libopenjp2-7-dev \
    libopenjp2-tools
```

#### macOS
```bash
brew install vips openjpeg
```

#### CentOS/RHEL
```bash
sudo yum install -y \
    vips-devel \
    openjpeg2-devel
```

## 验证安装

### 检查 libvips 是否支持 JPEG2000

```bash
# Linux/macOS
vips --version
# 查看输出中是否包含 "JPEG2000" 或 "openjpeg"

# 或使用 Python 测试
python -c "
import pyvips
print('libvips version:', pyvips.version(0))
# 尝试加载一个 JPEG2000 文件（如果有）
try:
    img = pyvips.Image.new_from_file('test.jp2')
    print('JPEG2000 support: OK')
except:
    print('JPEG2000 support: Not available or no test file')
"
```

### 检查已安装的格式支持

```bash
# Linux
vips list classes | grep -i jpeg
# 应该看到 jp2kload, jp2ksave 等

# 或
vips --help | grep -i jpeg
```

## 已更新的文件

1. ✅ `Dockerfile` - 添加了 `libopenjp2-7-dev` 和 `libopenjp2-tools`
2. ✅ `Dockerfile.optimized` - 添加了运行时依赖 `libopenjp2-7`

## 重新部署

### Railway

1. 提交更改：
```bash
git add Dockerfile Dockerfile.optimized
git commit -m "Add JPEG2000 support for SVS files (libopenjp2)"
git push
```

2. Railway 会自动重新构建和部署

3. 部署完成后，测试 SVS 文件上传

### 本地测试

1. 重新构建 Docker 镜像：
```bash
docker build -t dzi-converter .
```

2. 运行容器：
```bash
docker run -p 8000:8000 dzi-converter
```

3. 测试 SVS 文件上传

## 其他格式支持

如果需要支持更多格式，可以安装额外的库：

```dockerfile
# 完整格式支持（可选）
RUN apt-get install -y --no-install-recommends \
    libvips-dev \
    libopenjp2-7-dev \      # JPEG2000 (SVS, NDPI)
    libtiff-dev \           # TIFF (已包含在 libvips-dev 中)
    libpng-dev \            # PNG (已包含)
    libjpeg-dev \           # JPEG (已包含)
    libwebp-dev \           # WebP
    libheif-dev \           # HEIF/HEIC
    && rm -rf /var/lib/apt/lists/*
```

## 故障排除

### 如果仍然出现 JPEG2000 错误

1. **检查 libvips 版本**：
   ```bash
   vips --version
   ```
   确保版本 >= 8.10（较新版本默认包含更多格式支持）

2. **检查 openjpeg 库**：
   ```bash
   # Linux
   ldconfig -p | grep openjpeg
   # 应该看到 libopenjp2.so
   ```

3. **重新安装 libvips**：
   ```bash
   # Ubuntu/Debian
   sudo apt-get remove libvips-dev
   sudo apt-get install libvips-dev libopenjp2-7-dev
   ```

4. **验证 pyvips 安装**：
   ```bash
   pip uninstall pyvips
   pip install pyvips
   ```

## 参考

- [libvips 格式支持](https://www.libvips.org/API/current/VipsForeignSave.html)
- [openjpeg 项目](https://github.com/uclouvain/openjpeg)
- [SVS 文件格式](https://openslide.org/formats/aperio/)
