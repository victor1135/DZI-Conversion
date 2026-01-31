"""
Oxford Digital Pathology - DZI Conversion Backend
將病理切片轉換為 Deep Zoom Image (DZI) 格式並上傳到雲端
"""

import os
import sys
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from cloud_storage import S3Storage, OSSStorage

load_dotenv()

# 在導入 DZIConverter 之前，確保環境變數已設置
# 如果 .env 中有 VIPSHOME，設置 PATH
import platform
path_sep = ';' if platform.system() == 'Windows' else ':'

if 'VIPSHOME' in os.environ:
    vipshome = os.environ['VIPSHOME']
    bin_path = os.path.join(vipshome, 'bin')
    if os.path.exists(bin_path):
        os.environ['PATH'] = bin_path + path_sep + os.environ.get('PATH', '')
        print(f"[INFO] Set PATH for libvips: {bin_path}")

# 也檢查常見位置（僅 Windows）
if platform.system() == 'Windows' and 'VIPSHOME' not in os.environ:
    common_paths = [
        r"C:\vips-dev-8.15.0\bin",
        r"C:\vips-dev-8.14.0\bin",
        r"C:\vips-dev-8.13.0\bin",
    ]
    for path in common_paths:
        dll_path = Path(path) / "libvips-42.dll"
        if dll_path.exists():
            os.environ['PATH'] = path + path_sep + os.environ.get('PATH', '')
            os.environ['VIPSHOME'] = str(Path(path).parent)
            print(f"[INFO] Found libvips at: {path}")
            break

# DZIConverter 會自動處理 libvips 的載入
# 強制刷新輸出以確保啟動信息可見
import sys
sys.stdout.flush()

from dzi_converter import DZIConverter

# 驗證 pyvips 狀態
import dzi_converter
if dzi_converter.HAS_PYVIPS:
    print("[INFO] Application ready: pyvips is available for SVS conversion")
else:
    print("[WARNING] Application ready: pyvips not available - SVS files will fail")
sys.stdout.flush()

app = FastAPI(
    title="Oxford Pathology DZI Converter",
    description="Convert whole slide images to DZI format and upload to cloud storage",
    version="1.0.0"
)

# CORS 設定 - 允許前端訪問
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 暫存目錄
UPLOAD_DIR = Path("./uploads")
OUTPUT_DIR = Path("./output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 任務狀態追蹤
conversion_jobs = {}


class ConversionStatus(BaseModel):
    job_id: str
    status: str  # pending, converting, uploading, completed, failed
    progress: int  # 0-100
    message: str
    dzi_url: Optional[str] = None
    thumbnail_url: Optional[str] = None


class ConversionRequest(BaseModel):
    provider: str = "s3"  # s3 or oss
    bucket: Optional[str] = None
    region: Optional[str] = None


@app.get("/")
async def root():
    return {
        "service": "Oxford Pathology DZI Converter",
        "status": "running",
        "endpoints": {
            "upload": "POST /api/upload",
            "status": "GET /api/status/{job_id}",
            "health": "GET /api/health"
        }
    }


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/upload")
async def upload_slide(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    provider: str = "s3",
    bucket: Optional[str] = None,
    region: Optional[str] = None
):
    """
    上傳病理切片檔案，背景處理轉換和上傳
    
    支援格式: .svs, .tiff, .tif, .ndpi, .mrxs, .png, .jpg
    
    注意：大檔案（>100MB）可能需要較長時間，請耐心等待。
    可以使用 /api/status/{job_id} 查詢進度。
    """
    """
    上傳病理切片檔案，背景處理轉換和上傳
    
    支援格式: .svs, .tiff, .tif, .ndpi, .mrxs, .png, .jpg
    """
    # 驗證檔案類型
    allowed_extensions = {'.svs', '.tiff', '.tif', '.ndpi', '.mrxs', '.png', '.jpg', '.jpeg'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # 生成任務 ID
    job_id = str(uuid.uuid4())[:8]
    
    # 保存上傳的檔案
    upload_path = UPLOAD_DIR / f"{job_id}{file_ext}"
    
    # 性能監控：文件上傳階段
    import time
    upload_start = time.time()
    file_size = 0
    
    try:
        with open(upload_path, "wb") as buffer:
            content = await file.read()
            file_size = len(content)
            buffer.write(content)
        
        upload_elapsed = time.time() - upload_start
        upload_speed = file_size / upload_elapsed / 1024 / 1024  # MB/s
        print(f"[PERF] File upload: {file_size / 1024 / 1024:.2f} MB in {upload_elapsed:.2f}s ({upload_speed:.2f} MB/s)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # 初始化任務狀態
    conversion_jobs[job_id] = ConversionStatus(
        job_id=job_id,
        status="pending",
        progress=0,
        message="File uploaded, queued for conversion"
    )
    
    # 背景處理轉換
    background_tasks.add_task(
        process_conversion,
        job_id=job_id,
        input_path=upload_path,
        original_filename=file.filename,
        provider=provider,
        bucket=bucket or os.getenv("AWS_BUCKET", "2026-demo"),
        region=region or os.getenv("AWS_REGION", "eu-west-2")
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "File uploaded successfully. Conversion started.",
        "status_url": f"/api/status/{job_id}"
    }


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """取得轉換任務狀態"""
    try:
        if job_id not in conversion_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # 直接返回狀態，不進行任何阻塞操作
        status = conversion_jobs[job_id]
        return status
    except HTTPException:
        raise
    except Exception as e:
        # 如果發生任何意外錯誤，返回 500 而不是 timeout
        raise HTTPException(status_code=500, detail=f"Error retrieving status: {str(e)}")


@app.get("/api/jobs")
async def list_jobs():
    """列出所有任務"""
    return {"jobs": list(conversion_jobs.values())}


async def process_conversion(
    job_id: str,
    input_path: Path,
    original_filename: str,
    provider: str,
    bucket: str,
    region: str
):
    """
    背景任務：轉換 DZI 並上傳到雲端
    """
    import time
    from pathlib import Path
    
    # 嘗試導入 psutil（可選，用於系統資源監控）
    try:
        import psutil
        process = psutil.Process()
        HAS_PSUTIL = True
    except ImportError:
        HAS_PSUTIL = False
        print("[INFO] psutil not available - CPU/Memory monitoring disabled")
        print("       Install with: pip install psutil")
    
    # 性能監控：整體流程開始
    total_start = time.time()
    if HAS_PSUTIL:
        initial_cpu_percent = process.cpu_percent(interval=0.1)
        initial_memory_mb = process.memory_info().rss / 1024 / 1024
    else:
        initial_cpu_percent = 0
        initial_memory_mb = 0
    
    # 獲取輸入文件大小
    input_size_mb = input_path.stat().st_size / 1024 / 1024 if input_path.exists() else 0
    
    print(f"\n{'='*60}")
    print(f"[PERF] Job {job_id} started")
    print(f"[PERF] Input file: {original_filename} ({input_size_mb:.2f} MB)")
    print(f"[PERF] Initial CPU: {initial_cpu_percent:.1f}%, Memory: {initial_memory_mb:.2f} MB")
    print(f"{'='*60}")
    
    output_dir = OUTPUT_DIR / job_id
    
    try:
        # 確保環境變數在背景任務中也能正確設置
        path_sep = ';' if platform.system() == 'Windows' else ':'
        
        if 'VIPSHOME' in os.environ:
            vipshome = os.environ['VIPSHOME']
            bin_path = os.path.join(vipshome, 'bin')
            if os.path.exists(bin_path):
                os.environ['PATH'] = bin_path + path_sep + os.environ.get('PATH', '')
        
        # 也檢查常見位置（僅 Windows，背景任務中可能環境變數不同）
        if platform.system() == 'Windows' and ('VIPSHOME' not in os.environ or 'vips-dev' not in os.environ.get('PATH', '')):
            common_paths = [
                r"C:\vips-dev-8.15.0\bin",
                r"C:\vips-dev-8.14.0\bin",
                r"C:\vips-dev-8.13.0\bin",
            ]
            for path in common_paths:
                dll_path = Path(path) / "libvips-42.dll"
                if dll_path.exists():
                    os.environ['PATH'] = path + path_sep + os.environ.get('PATH', '')
                    os.environ['VIPSHOME'] = str(Path(path).parent)
                    print(f"[INFO] Background task: Found libvips at: {path}")
                    break
        
        # Step 1: 轉換為 DZI
        conversion_jobs[job_id].status = "converting"
        conversion_jobs[job_id].progress = 10
        conversion_jobs[job_id].message = "Converting to DZI format..."
        
        # 性能監控：轉換階段開始
        conversion_start = time.time()
        if HAS_PSUTIL:
            cpu_before = process.cpu_percent(interval=0.1)
            memory_before = process.memory_info().rss / 1024 / 1024
        else:
            cpu_before = 0
            memory_before = 0
        
        converter = DZIConverter()
        dzi_path, thumbnail_path = converter.convert(
            input_path=str(input_path),
            output_dir=str(output_dir),
            tile_size=256,
            overlap=1,
            format="jpeg",
            quality=85
        )
        
        # 性能監控：轉換階段結束
        conversion_elapsed = time.time() - conversion_start
        if HAS_PSUTIL:
            cpu_after = process.cpu_percent(interval=0.1)
            memory_after = process.memory_info().rss / 1024 / 1024
        else:
            cpu_after = 0
            memory_after = 0
        
        # 計算輸出文件大小
        dzi_size_mb = Path(dzi_path).stat().st_size / 1024 / 1024 if Path(dzi_path).exists() else 0
        tiles_dir = Path(dzi_path).with_suffix('').with_name(Path(dzi_path).stem + '_files')
        tiles_size_mb = sum(f.stat().st_size for f in tiles_dir.rglob('*') if f.is_file()) / 1024 / 1024 if tiles_dir.exists() else 0
        total_output_mb = dzi_size_mb + tiles_size_mb
        
        print(f"\n[PERF] Conversion stage completed:")
        print(f"  Time: {conversion_elapsed:.2f}s ({conversion_elapsed/60:.2f} min)")
        print(f"  Speed: {input_size_mb / conversion_elapsed:.2f} MB/s")
        print(f"  Output size: {total_output_mb:.2f} MB (DZI: {dzi_size_mb:.2f} MB, Tiles: {tiles_size_mb:.2f} MB)")
        print(f"  CPU usage: {cpu_before:.1f}% -> {cpu_after:.1f}%")
        print(f"  Memory usage: {memory_before:.2f} MB -> {memory_after:.2f} MB (+{memory_after - memory_before:.2f} MB)")
        
        conversion_jobs[job_id].progress = 50
        conversion_jobs[job_id].message = "DZI conversion completed. Uploading to cloud..."
        
        # Step 2: 上傳到雲端
        conversion_jobs[job_id].status = "uploading"
        
        # 性能監控：上傳階段開始
        upload_start = time.time()
        if HAS_PSUTIL:
            memory_before_upload = process.memory_info().rss / 1024 / 1024
        else:
            memory_before_upload = 0
        
        if provider == "s3":
            storage = S3Storage(
                bucket=bucket,
                region=region,
                is_public=os.getenv("S3_PUBLIC", "true").lower() == "true"
            )
        else:
            storage = OSSStorage(
                bucket=bucket,
                region=region,
                endpoint=os.getenv("OSS_ENDPOINT", "")
            )
        
        # 上傳 DZI 檔案和所有瓦片
        base_name = Path(original_filename).stem
        cloud_prefix = f"dzi/{job_id}/{base_name}"
        
        try:
            dzi_url, thumbnail_url = await storage.upload_dzi(
                dzi_path=dzi_path,
                thumbnail_path=thumbnail_path,
                cloud_prefix=cloud_prefix,
                on_progress=lambda p: update_progress(job_id, 50 + int(p * 0.5))
            )
            
            # 性能監控：上傳階段結束
            upload_elapsed = time.time() - upload_start
            if HAS_PSUTIL:
                memory_after_upload = process.memory_info().rss / 1024 / 1024
            else:
                memory_after_upload = 0
            upload_speed = total_output_mb / upload_elapsed if upload_elapsed > 0 else 0
            
            print(f"\n[PERF] Upload stage completed:")
            print(f"  Time: {upload_elapsed:.2f}s ({upload_elapsed/60:.2f} min)")
            print(f"  Speed: {upload_speed:.2f} MB/s")
            print(f"  Data uploaded: {total_output_mb:.2f} MB")
            print(f"  Memory usage: {memory_before_upload:.2f} MB -> {memory_after_upload:.2f} MB")
            
            # Step 3: 完成
            total_elapsed = time.time() - total_start
            if HAS_PSUTIL:
                final_cpu = process.cpu_percent(interval=0.1)
                final_memory = process.memory_info().rss / 1024 / 1024
            else:
                final_cpu = 0
                final_memory = 0
            
            print(f"\n{'='*60}")
            print(f"[PERF] Job {job_id} completed successfully")
            print(f"[PERF] Total time: {total_elapsed:.2f}s ({total_elapsed/60:.2f} min)")
            print(f"[PERF] Time breakdown:")
            print(f"  - Conversion: {conversion_elapsed:.2f}s ({conversion_elapsed/total_elapsed*100:.1f}%)")
            print(f"  - Upload: {upload_elapsed:.2f}s ({upload_elapsed/total_elapsed*100:.1f}%)")
            print(f"  - Other: {total_elapsed - conversion_elapsed - upload_elapsed:.2f}s")
            print(f"[PERF] Final CPU: {final_cpu:.1f}%, Memory: {final_memory:.2f} MB")
            print(f"{'='*60}\n")
            
            conversion_jobs[job_id].status = "completed"
            conversion_jobs[job_id].progress = 100
            conversion_jobs[job_id].message = "Conversion and upload completed successfully!"
            conversion_jobs[job_id].dzi_url = dzi_url
            conversion_jobs[job_id].thumbnail_url = thumbnail_url
        except Exception as upload_error:
            # 上傳失敗
            conversion_jobs[job_id].status = "failed"
            conversion_jobs[job_id].message = f"Upload failed: {str(upload_error)}"
            print(f"[ERROR] Upload failed for job {job_id}: {upload_error}")
            raise  # 重新拋出異常以便外層處理
        
    except ValueError as e:
        # 處理需要 pyvips 但未安裝的情況
        conversion_jobs[job_id].status = "failed"
        conversion_jobs[job_id].message = str(e)
        print(f"[ERROR] Conversion failed for job {job_id}: {e}")
        print(f"[DEBUG] VIPSHOME: {os.environ.get('VIPSHOME', 'Not set')}")
        print(f"[DEBUG] PATH contains vips: {'vips-dev' in os.environ.get('PATH', '')}")
        import sys
        sys.stdout.flush()
    except Exception as e:
        conversion_jobs[job_id].status = "failed"
        conversion_jobs[job_id].message = f"Error: {str(e)}"
        print(f"[ERROR] Conversion failed for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.stdout.flush()
    
    finally:
        # 清理暫存檔案
        try:
            if input_path.exists():
                input_path.unlink()
            if output_dir.exists():
                shutil.rmtree(output_dir)
        except Exception as e:
            print(f"Cleanup error: {e}")


def update_progress(job_id: str, progress: int):
    """更新任務進度"""
    if job_id in conversion_jobs:
        conversion_jobs[job_id].progress = min(progress, 99)


if __name__ == "__main__":
    import uvicorn
    # 設置 uvicorn，確保背景任務可以長時間運行，但保持 API 響應正常
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=True,
        timeout_keep_alive=75,  # 保持連接，但不要設為 0（會導致問題）
        timeout_graceful_shutdown=30  # 優雅關閉 timeout
    )



