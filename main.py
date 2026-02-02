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

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
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

# 優先檢查是否有帶 JPEG2000 支持的版本（僅 Windows）
# 即使 VIPSHOME 已設置，也要檢查是否有更好的版本
if platform.system() == 'Windows':
    # 優先檢查帶 JPEG2000 支持的版本
    common_paths = [
        r"C:\vips-dev-8.18\bin",      # 最新版本（包含所有格式，包括 JPEG2000）
        r"C:\vips-dev-8.18.0\bin",    # 最新版本（包含所有格式，包括 JPEG2000）
        r"C:\vips-dev-8.15.0\bin",
        r"C:\vips-dev-8.14.0\bin",
        r"C:\vips-dev-8.13.0\bin",
    ]
    
    # 先檢查是否有帶 JPEG2000 支持的版本
    found_jpeg2000_version = None
    for path in common_paths:
        dll_path = Path(path) / "libvips-42.dll"
        openjpeg_dll = Path(path) / "libopenjp2.dll"
        if dll_path.exists() and openjpeg_dll.exists():
            found_jpeg2000_version = path
            print(f"[INFO] Found libvips with JPEG2000 support at: {path}")
            break
    
    # 如果找到帶 JPEG2000 支持的版本，優先使用它
    if found_jpeg2000_version:
        os.environ['PATH'] = found_jpeg2000_version + path_sep + os.environ.get('PATH', '').replace(found_jpeg2000_version + path_sep, '')
        os.environ['VIPSHOME'] = str(Path(found_jpeg2000_version).parent)
        print(f"[INFO] Using libvips with JPEG2000 support: {found_jpeg2000_version}")
    elif 'VIPSHOME' in os.environ:
        # 如果沒有找到帶 JPEG2000 支持的版本，但 VIPSHOME 已設置，使用它
        vipshome = os.environ['VIPSHOME']
        bin_path = os.path.join(vipshome, 'bin')
        if os.path.exists(bin_path):
            os.environ['PATH'] = bin_path + path_sep + os.environ.get('PATH', '')
            print(f"[INFO] Set PATH for libvips: {bin_path}")
            print(f"[WARNING] This version may not have JPEG2000 support. Please install vips-dev-w64-all-*.zip")
    else:
        # 如果沒有 VIPSHOME 也沒有找到帶 JPEG2000 支持的版本，使用第一個找到的版本
        for path in common_paths:
            dll_path = Path(path) / "libvips-42.dll"
            if dll_path.exists():
                os.environ['PATH'] = path + path_sep + os.environ.get('PATH', '')
                os.environ['VIPSHOME'] = str(Path(path).parent)
                print(f"[INFO] Found libvips at: {path}")
                print(f"[WARNING] This version may not have JPEG2000 support. Please install vips-dev-w64-all-*.zip")
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

# 切片上傳追蹤（用於切片上傳模式）
chunk_uploads = {}  # {upload_id: {chunks: {}, total_chunks: int, filename: str, file_ext: str}}


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
        # 使用流式寫入，避免一次性加載整個文件到內存
        # 這對於大文件（>100MB）特別重要
        chunk_size = 1024 * 1024  # 1MB 塊
        import os
        with open(upload_path, "wb") as buffer:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                file_size += len(chunk)
                buffer.write(chunk)
            # 確保所有數據寫入磁盤緩衝區
            buffer.flush()
            # 強制同步到磁盤（確保文件完全寫入）
            if hasattr(buffer, 'fileno'):
                try:
                    os.fsync(buffer.fileno())
                except (OSError, AttributeError):
                    pass  # 某些系統可能不支持 fsync，忽略錯誤
        
        # 驗證文件完整性：檢查文件大小
        # 注意：FastAPI 的 UploadFile 可能沒有 Content-Length，所以我們只能檢查寫入的大小
        if upload_path.exists():
            actual_size = upload_path.stat().st_size
            if actual_size != file_size:
                raise HTTPException(
                    status_code=500,
                    detail=f"File size mismatch: expected {file_size} bytes, got {actual_size} bytes"
                )
        
        upload_elapsed = time.time() - upload_start
        upload_speed = file_size / upload_elapsed / 1024 / 1024 if upload_elapsed > 0 else 0  # MB/s
        print(f"[PERF] File upload completed: {file_size / 1024 / 1024:.2f} MB in {upload_elapsed:.2f}s ({upload_speed:.2f} MB/s)")
        print(f"[INFO] File saved to: {upload_path} ({file_size} bytes)")
        
        # 額外驗證：確保文件可以讀取（簡單的完整性檢查）
        try:
            with open(upload_path, "rb") as test_file:
                test_file.read(1)  # 讀取第一個字節驗證文件可讀
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"File verification failed: {str(e)}"
            )
            
    except HTTPException:
        # 重新拋出 HTTP 異常
        raise
    except Exception as e:
        # 如果上傳失敗，清理可能的部分文件
        if upload_path.exists():
            try:
                upload_path.unlink()
            except:
                pass
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


@app.post("/api/upload/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    filename: str = Form(...),
    chunk_size: Optional[int] = Form(None)
):
    """
    上傳文件切片（用於大文件切片上傳）
    
    參數:
    - chunk: 文件切片
    - upload_id: 上傳 ID（用於標識同一個文件的所有切片）
    - chunk_index: 切片索引（從 0 開始）
    - total_chunks: 總切片數
    - filename: 原始文件名
    - chunk_size: 切片大小（字節）
    """
    if not all([upload_id, chunk_index is not None, total_chunks, filename]):
        raise HTTPException(
            status_code=400,
            detail="Missing required parameters: upload_id, chunk_index, total_chunks, filename"
        )
    
    # 驗證檔案類型
    allowed_extensions = {'.svs', '.tiff', '.tif', '.ndpi', '.mrxs', '.png', '.jpg', '.jpeg'}
    file_ext = Path(filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # 初始化或獲取上傳記錄
    import time
    if upload_id not in chunk_uploads:
        chunk_uploads[upload_id] = {
            'chunks': {},
            'total_chunks': total_chunks,
            'filename': filename,
            'file_ext': file_ext,
            'created_at': time.time()
        }
    
    upload_info = chunk_uploads[upload_id]
    
    # 驗證參數一致性
    if upload_info['total_chunks'] != total_chunks or upload_info['filename'] != filename:
        raise HTTPException(
            status_code=400,
            detail="Upload parameters mismatch with existing upload session"
        )
    
    # 保存切片到臨時目錄
    chunk_dir = UPLOAD_DIR / "chunks" / upload_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_path = chunk_dir / f"chunk_{chunk_index}"
    
    try:
        # 讀取並保存切片
        chunk_data = await chunk.read()
        with open(chunk_path, "wb") as f:
            f.write(chunk_data)
        
        # 記錄切片
        import time
        upload_info['chunks'][chunk_index] = {
            'path': chunk_path,
            'size': len(chunk_data),
            'uploaded_at': time.time()
        }
        
        print(f"[INFO] Chunk {chunk_index + 1}/{total_chunks} uploaded for {upload_id} ({len(chunk_data) / 1024 / 1024:.2f} MB)")
        
        return {
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "chunk_size": len(chunk_data),
            "received_chunks": len(upload_info['chunks']),
            "total_chunks": total_chunks,
            "complete": len(upload_info['chunks']) == total_chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chunk: {str(e)}")


@app.post("/api/upload/complete")
async def complete_chunk_upload(
    background_tasks: BackgroundTasks,
    upload_id: str = Form(...),
    provider: str = Form("s3"),
    bucket: Optional[str] = Form(None),
    region: Optional[str] = Form(None)
):
    """
    完成切片上傳，合併所有切片並開始轉換
    
    參數:
    - upload_id: 上傳 ID
    - provider: 存儲提供商（s3 或 oss）
    - bucket: S3 bucket 名稱
    - region: AWS 區域
    """
    if upload_id not in chunk_uploads:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    upload_info = chunk_uploads[upload_id]
    total_chunks = upload_info['total_chunks']
    received_chunks = len(upload_info['chunks'])
    
    # 驗證所有切片都已上傳
    if received_chunks != total_chunks:
        missing_chunks = [i for i in range(total_chunks) if i not in upload_info['chunks']]
        raise HTTPException(
            status_code=400,
            detail=f"Not all chunks uploaded. Missing: {missing_chunks}. Received: {received_chunks}/{total_chunks}"
        )
    
    # 生成任務 ID
    job_id = str(uuid.uuid4())[:8]
    upload_path = UPLOAD_DIR / f"{job_id}{upload_info['file_ext']}"
    
    # 合併所有切片
    chunk_dir = UPLOAD_DIR / "chunks" / upload_id
    import time
    merge_start = time.time()
    total_size = 0
    
    try:
        print(f"[INFO] Merging {total_chunks} chunks for {upload_id}...")
        
        import os
        # 驗證所有切片文件都存在且大小正確
        expected_total_size = 0
        for i in range(total_chunks):
            chunk_path = chunk_dir / f"chunk_{i}"
            if not chunk_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail=f"Chunk {i} file not found"
                )
            expected_total_size += chunk_path.stat().st_size
        
        print(f"[INFO] Expected total size: {expected_total_size / 1024 / 1024:.2f} MB")
        
        # 按順序合併所有切片
        with open(upload_path, "wb") as output_file:
            for i in range(total_chunks):
                chunk_path = chunk_dir / f"chunk_{i}"
                chunk_file_size = chunk_path.stat().st_size
                
                with open(chunk_path, "rb") as chunk_file:
                    # 讀取整個切片
                    chunk_data = chunk_file.read()
                    
                    # 驗證切片大小
                    if len(chunk_data) != chunk_file_size:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Chunk {i} size mismatch: expected {chunk_file_size}, got {len(chunk_data)}"
                        )
                    
                    # 寫入合併文件
                    output_file.write(chunk_data)
                    total_size += len(chunk_data)
            
            # 確保所有數據寫入磁盤緩衝區
            output_file.flush()
            # 強制同步到磁盤（確保文件完全寫入）
            if hasattr(output_file, 'fileno'):
                try:
                    os.fsync(output_file.fileno())
                except (OSError, AttributeError):
                    pass  # 某些系統可能不支持 fsync，忽略錯誤
        
        merge_elapsed = time.time() - merge_start
        print(f"[PERF] Chunks merged: {total_size / 1024 / 1024:.2f} MB in {merge_elapsed:.2f}s")
        
        # 驗證合併後的文件
        if not upload_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Merged file was not created"
            )
        
        actual_file_size = upload_path.stat().st_size
        if actual_file_size != total_size or actual_file_size != expected_total_size:
            raise HTTPException(
                status_code=500,
                detail=f"File merge verification failed: expected {expected_total_size} bytes, got {actual_file_size} bytes"
            )
        
        # 額外驗證：嘗試讀取文件頭部，確保文件格式正確
        try:
            with open(upload_path, "rb") as test_file:
                header = test_file.read(16)  # 讀取前 16 字節
                if len(header) < 4:
                    raise HTTPException(
                        status_code=500,
                        detail="Merged file appears to be corrupted (too small)"
                    )
                print(f"[INFO] Merged file header check passed (first 16 bytes: {header[:4].hex()})")
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"File verification failed: {str(e)}"
            )
        
        # 清理切片文件
        try:
            import shutil
            shutil.rmtree(chunk_dir)
            del chunk_uploads[upload_id]
        except Exception as e:
            print(f"[WARNING] Failed to cleanup chunks: {e}")
        
        # 初始化任務狀態
        conversion_jobs[job_id] = ConversionStatus(
            job_id=job_id,
            status="pending",
            progress=0,
            message="File uploaded and merged, queued for conversion"
        )
        
        # 背景處理轉換
        background_tasks.add_task(
            process_conversion,
            job_id=job_id,
            input_path=upload_path,
            original_filename=upload_info['filename'],
            provider=provider,
            bucket=bucket or os.getenv("AWS_BUCKET", "2026-demo"),
            region=region or os.getenv("AWS_REGION", "eu-west-2")
        )
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "File uploaded and merged successfully. Conversion started.",
            "status_url": f"/api/status/{job_id}",
            "file_size": total_size
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # 清理失敗的合併
        if upload_path.exists():
            try:
                upload_path.unlink()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to merge chunks: {str(e)}")


@app.get("/api/upload/chunk/status/{upload_id}")
async def get_chunk_upload_status(upload_id: str):
    """查詢切片上傳狀態"""
    if upload_id not in chunk_uploads:
        raise HTTPException(status_code=404, detail="Upload session not found")
    
    upload_info = chunk_uploads[upload_id]
    received_chunks = len(upload_info['chunks'])
    total_chunks = upload_info['total_chunks']
    
    return {
        "upload_id": upload_id,
        "received_chunks": received_chunks,
        "total_chunks": total_chunks,
        "progress": (received_chunks / total_chunks * 100) if total_chunks > 0 else 0,
        "complete": received_chunks == total_chunks,
        "filename": upload_info['filename']
    }


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """取得轉換任務狀態"""
    try:
        if job_id not in conversion_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # 直接返回狀態，不進行任何阻塞操作
        status = conversion_jobs[job_id]
        # 確保返回字典格式（FastAPI 會自動序列化 Pydantic 模型，但明確轉換更安全）
        response = {
            "job_id": status.job_id,
            "status": status.status,
            "progress": status.progress,
            "message": status.message,
            "dzi_url": status.dzi_url,
            "thumbnail_url": status.thumbnail_url
        }
        # 調試：打印當前狀態（僅在開發環境）
        if os.getenv("DEBUG", "false").lower() == "true":
            print(f"[DEBUG] Status for {job_id}: {response}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        # 如果發生任何意外錯誤，返回 500 而不是 timeout
        import traceback
        print(f"[ERROR] Error retrieving status for {job_id}: {e}")
        traceback.print_exc()
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
    注意：確保文件完全上傳後才開始處理
    """
    # 等待一小段時間，確保文件完全寫入磁盤
    import asyncio
    await asyncio.sleep(0.5)  # 等待 500ms 確保文件系統同步
    
    # 驗證文件存在且可讀
    if not input_path.exists():
        conversion_jobs[job_id].status = "failed"
        conversion_jobs[job_id].message = f"Input file not found: {input_path}"
        print(f"[ERROR] Input file not found: {input_path}")
        return
    
    file_size = input_path.stat().st_size
    if file_size == 0:
        conversion_jobs[job_id].status = "failed"
        conversion_jobs[job_id].message = f"Input file is empty: {input_path}"
        print(f"[ERROR] Input file is empty: {input_path}")
        return
    
    print(f"[INFO] Starting conversion for file: {input_path} ({file_size / 1024 / 1024:.2f} MB)")
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
        print(f"[PROGRESS] Job {job_id}: Status updated to 'uploading', progress: 50%")
        
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
            # 定义进度回调函数，确保能正确更新进度
            def progress_callback(upload_progress: float):
                """上传进度回调：upload_progress 是 0.0 到 1.0 之间的浮点数"""
                try:
                    # 上传阶段占 50-100%，所以是 50 + upload_progress * 50
                    total_progress = 50 + int(upload_progress * 50)
                    update_progress(job_id, total_progress)
                    print(f"[DEBUG] Upload progress callback: {upload_progress:.2%} -> total progress: {total_progress}%")
                except Exception as e:
                    print(f"[ERROR] Error in progress callback: {e}")
            
            dzi_url, thumbnail_url = await storage.upload_dzi(
                dzi_path=dzi_path,
                thumbnail_path=thumbnail_path,
                cloud_prefix=cloud_prefix,
                on_progress=progress_callback
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
        old_progress = conversion_jobs[job_id].progress
        new_progress = min(progress, 99)
        conversion_jobs[job_id].progress = new_progress
        # 每次更新都打印（用于调试），但可以后续优化为只打印重要变化
        if new_progress != old_progress:
            print(f"[PROGRESS] Job {job_id}: {old_progress}% -> {new_progress}%")
    else:
        print(f"[WARNING] update_progress called for unknown job_id: {job_id}")


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



