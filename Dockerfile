# 使用官方 Python 運行時作為基礎鏡像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴（包括 libvips 和編譯工具）
# pyvips 需要從源碼編譯，所以需要 gcc 等編譯工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    make \
    python3-dev \
    libvips-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴
# pyvips 會在這裡編譯
RUN pip install --no-cache-dir -r requirements.txt

# 可選：清理編譯工具以減小鏡像大小（如果不需要編譯其他包）
# 注意：如果以後需要安裝其他需要編譯的 Python 包，需要保留這些工具
# RUN apt-get purge -y build-essential gcc g++ make python3-dev pkg-config && \
#     apt-get autoremove -y && \
#     rm -rf /var/lib/apt/lists/*

# 複製應用程序代碼
COPY . .

# 暴露端口（Railway 會自動設置 PORT 環境變數）
EXPOSE 8000

# 啟動命令（Railway 會自動設置 PORT 環境變數）
# 使用 shell 形式以支持環境變數
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
