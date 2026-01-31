# 使用官方 Python 運行時作為基礎鏡像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴（包括 libvips）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libvips-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程序代碼
COPY . .

# 暴露端口（Railway 會自動設置 PORT 環境變數）
EXPOSE 8000

# 啟動命令（Railway 會自動設置 PORT 環境變數）
# 使用 shell 形式以支持環境變數
CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
