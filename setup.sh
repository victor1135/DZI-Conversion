#!/bin/bash
# Railway 部署腳本 - 自動安裝 libvips (Linux)

set -e  # 遇到錯誤立即退出

echo "=========================================="
echo "Setting up environment for Railway..."
echo "=========================================="

# 檢測操作系統
OS="$(uname -s)"
echo "Detected OS: $OS"

# 在 Linux 環境下安裝 libvips
if [[ "$OS" == "Linux" ]]; then
    echo "Installing libvips for Linux..."
    
    # 檢查是否已安裝
    if command -v vips &> /dev/null; then
        echo "libvips is already installed"
        vips --version
    else
        # 嘗試使用 apt-get (Ubuntu/Debian)
        if command -v apt-get &> /dev/null; then
            echo "Installing libvips using apt-get..."
            sudo apt-get update -qq
            sudo apt-get install -y -qq libvips-dev
        # 嘗試使用 yum (CentOS/RHEL)
        elif command -v yum &> /dev/null; then
            echo "Installing libvips using yum..."
            sudo yum install -y -q vips-devel
        # 嘗試使用 apk (Alpine)
        elif command -v apk &> /dev/null; then
            echo "Installing libvips using apk..."
            sudo apk add --no-cache vips-dev
        else
            echo "WARNING: Could not detect package manager. libvips may not be installed."
            echo "Please install libvips manually for your Linux distribution."
        fi
    fi
    
    # 驗證安裝
    if command -v vips &> /dev/null; then
        echo "✓ libvips installed successfully"
        vips --version
    else
        echo "✗ libvips installation failed or not found"
        echo "The application will still work but SVS files may not be supported."
    fi
else
    echo "Non-Linux environment detected. Skipping libvips installation."
    echo "Note: Railway runs on Linux containers, so this should not happen."
fi

echo ""
echo "=========================================="
echo "Environment setup complete!"
echo "=========================================="
