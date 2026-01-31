"""
Cloud Storage - 上傳 DZI 到 S3 或 OSS
"""

import os
import asyncio
from pathlib import Path
from typing import Tuple, Callable, Optional
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore.config import Config
import boto3.s3.transfer
import requests


class S3Storage:
    """
    AWS S3 儲存服務
    支援 Public Bucket 和 Private Bucket
    """
    
    def __init__(
        self,
        bucket: str,
        region: str = "eu-west-2",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        is_public: bool = True
    ):
        self.bucket = bucket
        self.region = region
        self.is_public = is_public
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        
        # S3 基础 URL
        self.base_url = f"https://{bucket}.s3.{region}.amazonaws.com"
        
        # 如果有凭证，创建 boto3 client（用于有凭证上传）
        if self.access_key and self.secret_key:
            self.client = boto3.client(
                's3',
                region_name=region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
        else:
            self.client = None
    
    async def upload_dzi(
        self,
        dzi_path: str,
        thumbnail_path: str,
        cloud_prefix: str,
        on_progress: Optional[Callable[[float], None]] = None
    ) -> Tuple[str, str]:
        """
        上傳 DZI 檔案和所有瓦片到 S3
        
        Args:
            dzi_path: 本地 DZI 檔案路徑
            thumbnail_path: 縮圖路徑
            cloud_prefix: 雲端路徑前綴 (e.g., "dzi/job123/slide")
            on_progress: 進度回調函數 (0.0 - 1.0)
        
        Returns:
            (dzi_url, thumbnail_url)
        """
        dzi_file = Path(dzi_path)
        tiles_dir = dzi_file.with_suffix('').with_name(dzi_file.stem + '_files')
        
        # 收集所有需要上傳的檔案
        files_to_upload = []
        
        # DZI 描述檔
        files_to_upload.append((
            str(dzi_file),
            f"{cloud_prefix}.dzi",
            "application/xml"
        ))
        
        # 縮圖
        if os.path.exists(thumbnail_path):
            files_to_upload.append((
                thumbnail_path,
                f"{cloud_prefix}_thumbnail.jpg",
                "image/jpeg"
            ))
        
        # 所有瓦片
        if tiles_dir.exists():
            levels_found = []
            # 確保按數字順序排序層級目錄
            level_dirs = []
            for item in tiles_dir.iterdir():
                if item.is_dir() and item.name.isdigit():
                    level_dirs.append((int(item.name), item))
            
            # 按層級數字排序
            level_dirs.sort(key=lambda x: x[0])
            
            print(f"[INFO] Found {len(level_dirs)} level directories")
            
            for level_num, level_dir in level_dirs:
                levels_found.append(level_num)
                tile_count = 0
                tile_files = []
                for tile_file in level_dir.iterdir():
                    if tile_file.is_file():
                        tile_files.append(tile_file)
                
                # 確保瓦片按順序處理
                tile_files.sort(key=lambda x: x.name)
                
                for tile_file in tile_files:
                    tile_count += 1
                    cloud_key = f"{cloud_prefix}_files/{level_dir.name}/{tile_file.name}"
                    content_type = "image/jpeg" if tile_file.suffix in ['.jpg', '.jpeg'] else "image/png"
                    files_to_upload.append((
                        str(tile_file),
                        cloud_key,
                        content_type
                    ))
                
                if tile_count > 0:
                    print(f"[INFO] Level {level_num}: {tile_count} tiles")
                else:
                    print(f"[WARNING] Level {level_num}: no tiles found!")
            
            if levels_found:
                print(f"[INFO] Uploading {len(levels_found)} levels: {min(levels_found)} to {max(levels_found)}")
                print(f"[INFO] Total files to upload: {len(files_to_upload)} (DZI + thumbnail + tiles)")
                
                # 檢查是否有缺失的層級
                expected_levels = set(range(min(levels_found), max(levels_found) + 1))
                actual_levels = set(levels_found)
                missing_levels = expected_levels - actual_levels
                if missing_levels:
                    print(f"[WARNING] Missing levels: {sorted(missing_levels)}")
                    print(f"[WARNING] This may cause issues with OpenSeadragon viewer")
        
        total_files = len(files_to_upload)
        uploaded = 0
        
        # 性能監控：計算總文件大小
        import time
        upload_start = time.time()
        total_size_bytes = 0
        for local_path, _, _ in files_to_upload:
            if os.path.exists(local_path):
                total_size_bytes += os.path.getsize(local_path)
        total_size_mb = total_size_bytes / 1024 / 1024
        
        print(f"\n[PERF] Upload stage started:")
        print(f"  Total files: {total_files}")
        print(f"  Total size: {total_size_mb:.2f} MB")
        print(f"  Average file size: {total_size_mb / total_files * 1024:.2f} KB")
        
        # 優化的 boto3 配置
        # 對於大量小文件，使用 put_object 比 upload_file 更快（減少開銷）
        config = Config(
            connect_timeout=30,
            read_timeout=60,  # 小文件上傳很快，不需要很長的超時
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=100  # 增加連接池大小以支持更多並行連接
        )
        
        # 決定使用哪種上傳方式
        use_http_put = self.is_public and not (self.access_key and self.secret_key)
        
        shared_client = None
        transfer_config = None
        
        if use_http_put:
            print("[INFO] Using direct HTTP PUT requests (no credentials, public bucket)")
        elif self.access_key and self.secret_key:
            # 有凭证，使用 boto3
            shared_client = boto3.client(
                's3',
                region_name=self.region,
                config=config,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
            print("[INFO] Using boto3 with credentials")
            
            # 對於大文件（>5MB），使用 upload_file with multipart
            # 對於小文件，使用 put_object（更快，開銷更小）
            transfer_config = boto3.s3.transfer.TransferConfig(
                multipart_threshold=1024 * 5,  # 5MB 以上使用 multipart
                max_concurrency=10,
                multipart_chunksize=1024 * 5,
                use_threads=True,
                max_bandwidth=None
            )
        else:
            raise ValueError("No credentials provided and bucket is not public. Cannot upload.")
        
        # 並行上傳函數
        def upload_file(args):
            local_path, cloud_key, content_type = args
            try:
                if not os.path.exists(local_path):
                    error_msg = f"File not found: {local_path}"
                    print(f"[ERROR] {error_msg}")
                    return False, (cloud_key, error_msg)
                
                file_size = os.path.getsize(local_path)
                
                if use_http_put:
                    # 使用直接 HTTP PUT 請求（無簽名，適用於 public bucket）
                    s3_url = f"{self.base_url}/{cloud_key}"
                    
                    with open(local_path, 'rb') as f:
                        response = requests.put(
                            s3_url,
                            data=f,
                            headers={
                                'Content-Type': content_type,
                            },
                            timeout=(30, 60)  # (connect_timeout, read_timeout)
                        )
                    
                    if response.status_code == 200:
                        return True, cloud_key
                    else:
                        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                        print(f"[ERROR] Failed to upload {cloud_key}: {error_msg}")
                        return False, (cloud_key, error_msg)
                else:
                    # 使用 boto3（有凭证）
                    # 小文件（<5MB）使用 put_object（更快）
                    if file_size < 5 * 1024 * 1024:
                        with open(local_path, 'rb') as f:
                            shared_client.put_object(
                                Bucket=self.bucket,
                                Key=cloud_key,
                                Body=f,
                                ContentType=content_type
                            )
                    else:
                        # 大文件使用 upload_file with multipart
                        shared_client.upload_file(
                            local_path,
                            self.bucket,
                            cloud_key,
                            ExtraArgs={'ContentType': content_type},
                            Config=transfer_config
                        )
                    return True, cloud_key
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                print(f"[ERROR] Failed to upload {cloud_key}: {error_type}: {error_msg}")
                # 如果是认证错误，提供更详细的提示
                if 'AccessDenied' in error_msg or 'InvalidAccessKeyId' in error_msg or 'SignatureDoesNotMatch' in error_msg:
                    print(f"[ERROR] Authentication error - check AWS credentials or bucket permissions")
                elif 'NoCredentialsError' in error_type or 'credentials' in error_msg.lower():
                    print(f"[ERROR] No AWS credentials found - set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
                return False, (cloud_key, error_msg)
        
        # 大幅增加並行度 - 對於大量小文件，可以設置更高的並行度
        # S3 支持高並發，但要注意不要超過網絡帶寬
        # 根據文件數量動態調整：文件越多，並行度越高
        if total_files > 50000:
            max_workers = 100  # 超大量文件
        elif total_files > 10000:
            max_workers = 50   # 大量文件
        elif total_files > 1000:
            max_workers = 30   # 中等數量
        else:
            max_workers = 20   # 少量文件
        
        print(f"[PERF] Using {max_workers} parallel workers for upload")
        
        # 使用線程池並行上傳
        failed_uploads = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(executor, upload_file, args)
                for args in files_to_upload
            ]
            
            for i, future in enumerate(asyncio.as_completed(futures)):
                try:
                    result = await future
                    if isinstance(result, tuple):
                        success, result_data = result
                        if isinstance(result_data, tuple):
                            # 新格式：(cloud_key, error_msg)
                            cloud_key, error_msg = result_data
                        else:
                            # 舊格式：只有 cloud_key
                            cloud_key = result_data
                            error_msg = None
                    else:
                        # 向後兼容舊版本
                        success = result
                        cloud_key = files_to_upload[i][1] if i < len(files_to_upload) else "unknown"
                        error_msg = None
                    
                    if success:
                        uploaded += 1
                    else:
                        failed_uploads.append((cloud_key, error_msg))
                    
                    if on_progress:
                        on_progress(uploaded / total_files)
                    
                    # 每上傳 100 個檔案輸出一次進度
                    if uploaded % 100 == 0:
                        elapsed = time.time() - upload_start
                        progress_pct = uploaded * 100 // total_files
                        if elapsed > 0:
                            speed = (uploaded / total_files * total_size_mb) / elapsed
                            eta = (total_files - uploaded) * elapsed / uploaded if uploaded > 0 else 0
                            print(f"[INFO] Upload progress: {uploaded}/{total_files} ({progress_pct}%) | "
                                  f"Speed: {speed:.2f} MB/s | ETA: {eta/60:.1f} min")
                        else:
                            print(f"[INFO] Upload progress: {uploaded}/{total_files} ({progress_pct}%)")
                except Exception as e:
                    print(f"[ERROR] Error processing upload result: {e}")
                    import traceback
                    traceback.print_exc()
                    failed_uploads.append((f"unknown_{i}", str(e)))
        
        # 檢查是否有失敗的上傳
        if failed_uploads:
            print(f"[WARNING] {len(failed_uploads)} files failed to upload:")
            
            # 統計錯誤類型
            error_types = {}
            for item in failed_uploads:
                if isinstance(item, tuple):
                    cloud_key, error_msg = item
                    if error_msg:
                        # 提取錯誤類型（第一個單詞或常見錯誤關鍵字）
                        if 'AccessDenied' in error_msg:
                            error_type = 'AccessDenied'
                        elif 'InvalidAccessKeyId' in error_msg or 'NoCredentialsError' in error_msg:
                            error_type = 'Authentication'
                        elif 'NoSuchBucket' in error_msg:
                            error_type = 'BucketNotFound'
                        elif 'Network' in error_msg or 'timeout' in error_msg.lower():
                            error_type = 'Network'
                        else:
                            error_type = 'Other'
                        error_types[error_type] = error_types.get(error_type, 0) + 1
                else:
                    cloud_key = item
                    error_types['Unknown'] = error_types.get('Unknown', 0) + 1
            
            # 顯示錯誤統計
            if error_types:
                print(f"[ERROR] Error summary:")
                for error_type, count in error_types.items():
                    print(f"  - {error_type}: {count} files")
            
            # 顯示前10個失敗的文件和錯誤信息
            for item in failed_uploads[:10]:
                if isinstance(item, tuple):
                    cloud_key, error_msg = item
                    if error_msg:
                        print(f"  - {cloud_key}: {error_msg[:100]}")  # 限制錯誤信息長度
                    else:
                        print(f"  - {cloud_key}")
                else:
                    print(f"  - {item}")
            
            if len(failed_uploads) > 10:
                print(f"  ... and {len(failed_uploads) - 10} more")
            
            # 提供診斷建議
            if 'Authentication' in error_types or 'AccessDenied' in error_types:
                print(f"\n[DIAGNOSIS] Authentication/Authorization errors detected.")
                print(f"  - Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
                print(f"  - Verify bucket permissions and IAM policy")
                print(f"  - For public buckets, ensure bucket policy allows uploads")
            elif 'BucketNotFound' in error_types:
                print(f"\n[DIAGNOSIS] Bucket not found.")
                print(f"  - Verify bucket name: {self.bucket}")
                print(f"  - Check region: {self.region}")
            
            raise Exception(f"Failed to upload {len(failed_uploads)} files out of {total_files}")
        
        # 性能監控：上傳階段結束
        upload_elapsed = time.time() - upload_start
        upload_speed = total_size_mb / upload_elapsed if upload_elapsed > 0 else 0
        files_per_sec = total_files / upload_elapsed if upload_elapsed > 0 else 0
        
        print(f"\n[PERF] Upload stage completed:")
        print(f"  Time: {upload_elapsed:.2f}s ({upload_elapsed/60:.2f} min)")
        print(f"  Speed: {upload_speed:.2f} MB/s")
        print(f"  Throughput: {files_per_sec:.1f} files/sec")
        print(f"  Total uploaded: {total_size_mb:.2f} MB ({total_files} files)")
        
        dzi_url = f"{self.base_url}/{cloud_prefix}.dzi"
        thumbnail_url = f"{self.base_url}/{cloud_prefix}_thumbnail.jpg"
        
        return dzi_url, thumbnail_url


class OSSStorage:
    """
    阿里雲 OSS 儲存服務
    """
    
    def __init__(
        self,
        bucket: str,
        region: str,
        endpoint: str,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None
    ):
        import oss2
        
        self.bucket_name = bucket
        self.region = region
        self.endpoint = endpoint
        
        auth = oss2.Auth(
            access_key or os.getenv("OSS_ACCESS_KEY_ID"),
            secret_key or os.getenv("OSS_ACCESS_KEY_SECRET")
        )
        self.bucket = oss2.Bucket(auth, endpoint, bucket)
        self.base_url = f"https://{bucket}.{endpoint}"
    
    async def upload_dzi(
        self,
        dzi_path: str,
        thumbnail_path: str,
        cloud_prefix: str,
        on_progress: Optional[Callable[[float], None]] = None
    ) -> Tuple[str, str]:
        """
        上傳 DZI 檔案和所有瓦片到 OSS
        """
        dzi_file = Path(dzi_path)
        tiles_dir = dzi_file.with_suffix('').with_name(dzi_file.stem + '_files')
        
        files_to_upload = []
        
        # DZI 描述檔
        files_to_upload.append((str(dzi_file), f"{cloud_prefix}.dzi"))
        
        # 縮圖
        if os.path.exists(thumbnail_path):
            files_to_upload.append((thumbnail_path, f"{cloud_prefix}_thumbnail.jpg"))
        
        # 所有瓦片
        if tiles_dir.exists():
            for level_dir in sorted(tiles_dir.iterdir()):
                if level_dir.is_dir():
                    for tile_file in level_dir.iterdir():
                        if tile_file.is_file():
                            cloud_key = f"{cloud_prefix}_files/{level_dir.name}/{tile_file.name}"
                            files_to_upload.append((str(tile_file), cloud_key))
        
        total_files = len(files_to_upload)
        uploaded = 0
        
        def upload_file(args):
            local_path, cloud_key = args
            try:
                self.bucket.put_object_from_file(cloud_key, local_path)
                return True
            except Exception as e:
                print(f"Failed to upload {cloud_key}: {e}")
                return False
        
        with ThreadPoolExecutor(max_workers=20) as executor:  # 增加並行度
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(executor, upload_file, args)
                for args in files_to_upload
            ]
            
            for future in asyncio.as_completed(futures):
                await future
                uploaded += 1
                if on_progress:
                    on_progress(uploaded / total_files)
        
        dzi_url = f"{self.base_url}/{cloud_prefix}.dzi"
        thumbnail_url = f"{self.base_url}/{cloud_prefix}_thumbnail.jpg"
        
        return dzi_url, thumbnail_url



