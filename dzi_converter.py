"""
DZI Converter - 將圖片轉換為 Deep Zoom Image 格式

支援兩種轉換引擎：
1. pyvips (需要系統安裝 libvips) - 適合大型病理切片
2. Pillow (純 Python) - 適合一般圖片，無需額外依賴
"""

import os
import math
import sys
from pathlib import Path
from typing import Tuple, Optional

# 嘗試從 .env 讀取 VIPSHOME（如果可用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv 是可選的

# 嘗試導入 pyvips (需要系統安裝 libvips)
HAS_PYVIPS = False
pyvips = None


def _try_find_libvips():
    """嘗試在常見位置找到 libvips 並設置環境變數"""
    import platform
    
    # 獲取平台特定的路徑分隔符
    path_sep = ';' if platform.system() == 'Windows' else ':'
    is_windows = platform.system() == 'Windows'
    
    # 檢查環境變數
    if 'VIPSHOME' in os.environ:
        vipshome = os.environ['VIPSHOME']
        bin_path = os.path.join(vipshome, 'bin')
        if os.path.exists(bin_path):
            os.environ['PATH'] = bin_path + path_sep + os.environ.get('PATH', '')
            return True
    
    # Windows 常見安裝位置
    if is_windows:
        common_paths = [
            r"C:\vips-dev-8.15.0\bin",
            r"C:\vips-dev-8.14.0\bin",
            r"C:\vips-dev-8.13.0\bin",
            r"C:\vips-dev-8.12.0\bin",
            r"D:\vips-dev-8.15.0\bin",
            r"D:\libs\vips-dev-8.15.0\bin",
        ]
        
        for path in common_paths:
            dll_path = Path(path) / "libvips-42.dll"
            if dll_path.exists():
                os.environ['PATH'] = path + path_sep + os.environ.get('PATH', '')
                return True
    else:
        # Linux/macOS: libvips 通常安裝在系統路徑中，pyvips 應該能自動找到
        # 檢查常見的系統庫路徑
        common_paths = [
            '/usr/lib',
            '/usr/local/lib',
            '/opt/homebrew/lib',  # macOS Apple Silicon
            '/usr/lib/x86_64-linux-gnu',  # Debian/Ubuntu
        ]
        
        for path in common_paths:
            # 檢查是否有 libvips 相關的 .so 文件
            if os.path.exists(path):
                vips_libs = list(Path(path).glob('libvips*.so*'))
                if vips_libs:
                    # 在 Linux 上，通常不需要手動設置 PATH
                    # pyvips 會通過系統的動態鏈接器找到庫
                    return True
    
    return False


def _try_load_pyvips():
    """嘗試載入 pyvips"""
    global HAS_PYVIPS, pyvips
    
    try:
        import pyvips as _pyvips
        # 測試是否真的能用
        _pyvips.Image.black(1, 1)
        pyvips = _pyvips
        HAS_PYVIPS = True
        return True
    except (ImportError, OSError) as e:
        # 輸出詳細錯誤信息以便調試
        print(f"[DEBUG] Failed to load pyvips: {type(e).__name__}: {e}")
        return False


# 第一次嘗試載入
if not _try_load_pyvips():
    # 如果失敗，嘗試找到 libvips
    if _try_find_libvips():
        # 清除已導入的模組並重新嘗試
        if 'pyvips' in sys.modules:
            del sys.modules['pyvips']
        _try_load_pyvips()

# 配置 libvips 以充分利用多核心 CPU
if HAS_PYVIPS:
    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
    # 設置並行度：通常為 CPU 核心數的 1-2 倍（考慮超線程）
    # 但不要設置太高，避免線程競爭
    vips_threads = min(cpu_count * 2, 16)  # 最多 16 個線程
    
    # 設置 libvips 環境變數以充分利用 CPU
    os.environ['VIPS_CONCURRENCY'] = str(vips_threads)
    # 增加緩存大小以提高大文件處理速度（MB）
    if 'VIPS_MAX_CACHE' not in os.environ:
        os.environ['VIPS_MAX_CACHE'] = '500'  # 500MB 緩存
    
    print("[OK] pyvips available - using libvips for high-performance conversion")
    print(f"[INFO] libvips configured: {vips_threads} threads (CPU cores: {cpu_count})")
else:
    print("[INFO] pyvips not available")
    print("       Using PIL fallback - works for TIFF/PNG/JPEG (not SVS/NDPI)")

from PIL import Image


class DZIConverter:
    """
    Deep Zoom Image 轉換器
    
    將大型圖片轉換為金字塔式瓦片結構，適用於 OpenSeadragon 等檢視器
    """
    
    def __init__(self):
        self.use_vips = HAS_PYVIPS
    
    def convert(
        self,
        input_path: str,
        output_dir: str,
        tile_size: int = 256,
        overlap: int = 1,
        format: str = "jpeg",
        quality: int = 85
    ) -> Tuple[str, str]:
        """
        轉換圖片為 DZI 格式
        
        Args:
            input_path: 輸入圖片路徑
            output_dir: 輸出目錄
            tile_size: 瓦片大小 (預設 256)
            overlap: 瓦片重疊像素 (預設 1)
            format: 輸出格式 (jpeg/png)
            quality: JPEG 品質 (0-100)
        
        Returns:
            (dzi_path, thumbnail_path) - DZI 檔案路徑和縮圖路徑
        
        Raises:
            ValueError: 如果檔案格式需要 pyvips 但未安裝
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 檢查是否需要 pyvips 的特殊格式
        file_ext = Path(input_path).suffix.lower()
        requires_vips = file_ext in {'.svs', '.ndpi', '.mrxs', '.vms', '.vmu', '.scn', '.bif'}
        
        if requires_vips and not self.use_vips:
            # 最後一次嘗試：動態搜尋並載入
            print(f"[DEBUG] SVS file detected, attempting to load libvips...")
            print(f"[DEBUG] Current use_vips: {self.use_vips}, HAS_PYVIPS: {HAS_PYVIPS}")
            
            # 先嘗試找到 libvips
            found = _try_find_libvips()
            print(f"[DEBUG] _try_find_libvips returned: {found}")
            
            if found:
                # 清除已導入的模組
                if 'pyvips' in sys.modules:
                    print("[DEBUG] Removing pyvips from sys.modules")
                    del sys.modules['pyvips']
                
                # 嘗試載入
                loaded = _try_load_pyvips()
                print(f"[DEBUG] _try_load_pyvips returned: {loaded}")
                
                if loaded:
                    # 更新實例變數和全局狀態
                    self.use_vips = HAS_PYVIPS
                    print(f"[OK] Found libvips dynamically, now processing {file_ext}")
            
            if not self.use_vips or pyvips is None:
                raise ValueError(
                    f"檔案格式 {file_ext} 需要 pyvips (libvips) 才能處理。\n\n"
                    "安裝步驟：\n"
                    "1. 下載 libvips: https://github.com/libvips/libvips/releases\n"
                    "   Windows: 下載 vips-dev-w64-web-*.zip\n"
                    "   macOS: brew install vips\n"
                    "   Linux: apt-get install libvips-dev\n\n"
                    "2. 解壓縮到固定位置（Windows），例如: C:\\vips-dev-8.15.0\\\n\n"
                    "3. 設置環境變數:\n"
                    "   - 方法1: 系統環境變數 Path 中新增: C:\\vips-dev-8.15.0\\bin\n"
                    "   - 方法2: 設置 VIPSHOME=C:\\vips-dev-8.15.0\n"
                    "   - 方法3: 在代碼開頭添加: os.environ['PATH'] = r'C:\\vips-dev-8.15.0\\bin' + ';' + os.environ['PATH']\n\n"
                    "4. 重新啟動應用程式\n\n"
                    "詳細說明請查看: INSTALL_LIBVIPS.md"
                )
        
        base_name = Path(input_path).stem
        dzi_path = os.path.join(output_dir, f"{base_name}.dzi")
        tiles_dir = os.path.join(output_dir, f"{base_name}_files")
        thumbnail_path = os.path.join(output_dir, f"{base_name}_thumbnail.jpg")
        
        if self.use_vips:
            self._convert_with_vips(
                input_path, dzi_path, tiles_dir,
                tile_size, overlap, format, quality
            )
        else:
            self._convert_with_pil(
                input_path, dzi_path, tiles_dir,
                tile_size, overlap, format, quality
            )
        
        # 生成縮圖
        self._create_thumbnail(input_path, thumbnail_path)
        
        return dzi_path, thumbnail_path
    
    def _convert_with_vips(
        self,
        input_path: str,
        dzi_path: str,
        tiles_dir: str,
        tile_size: int,
        overlap: int,
        format: str,
        quality: int
    ):
        """使用 libvips 進行高效能轉換 (推薦用於大檔案)"""
        if pyvips is None:
            raise RuntimeError("pyvips is not available. Please install libvips.")
        
        # 性能監控：轉換階段開始
        import time
        conversion_start = time.time()
        input_size_mb = os.path.getsize(input_path) / 1024 / 1024 if os.path.exists(input_path) else 0
        
        print(f"[PERF] Starting DZI conversion:")
        print(f"  Input file: {os.path.basename(input_path)} ({input_size_mb:.2f} MB)")
        
        # 讀取圖像
        image_load_start = time.time()
        image = pyvips.Image.new_from_file(input_path)
        image_load_time = time.time() - image_load_start
        
        # 獲取圖像尺寸
        width = image.width
        height = image.height
        print(f"  Image size: {width}x{height} pixels")
        print(f"  Image load time: {image_load_time:.2f}s")
        
        # 設定輸出選項
        suffix = f".{format}"
        if format == "jpeg":
            suffix = f".jpg[Q={quality}]"
        
        # 使用 dzsave 生成 DZI
        # 注意：不設置 depth 參數，讓 libvips 自動計算所有需要的層級
        # depth='onetile' 會限制層級數，導致上層縮圖缺失
        # libvips 會自動使用多線程來並行處理瓦片生成
        dzsave_start = time.time()
        
        image.dzsave(
            dzi_path.replace('.dzi', ''),
            tile_size=tile_size,
            overlap=overlap,
            suffix=suffix,
            properties=True
        )
        
        dzsave_time = time.time() - dzsave_start
        total_time = time.time() - conversion_start
        
        # 驗證生成的層級數和文件大小
        tiles_dir = Path(dzi_path.replace('.dzi', '_files'))
        dzi_size_mb = os.path.getsize(dzi_path) / 1024 / 1024 if os.path.exists(dzi_path) else 0
        
        if tiles_dir.exists():
            levels = sorted([int(d.name) for d in tiles_dir.iterdir() if d.is_dir() and d.name.isdigit()])
            tile_count = sum(len(list(level_dir.iterdir())) for level_dir in tiles_dir.iterdir() if level_dir.is_dir())
            tiles_size_mb = sum(f.stat().st_size for f in tiles_dir.rglob('*') if f.is_file()) / 1024 / 1024
            
            print(f"[PERF] DZI conversion completed:")
            print(f"  Total time: {total_time:.2f}s ({total_time/60:.2f} min)")
            print(f"  - Image load: {image_load_time:.2f}s")
            print(f"  - dzsave: {dzsave_time:.2f}s ({dzsave_time/total_time*100:.1f}%)")
            print(f"  Processing speed: {input_size_mb / total_time:.2f} MB/s")
            print(f"  Generated: {len(levels)} levels, {tile_count} tiles")
            print(f"  Output size: {dzi_size_mb + tiles_size_mb:.2f} MB (DZI: {dzi_size_mb:.2f} MB, Tiles: {tiles_size_mb:.2f} MB)")
        else:
            print(f"[PERF] DZI conversion completed in {total_time:.2f}s ({total_time/60:.2f} min)")
        
        print(f"DZI created with vips: {dzi_path}")
    
    def _convert_with_pil(
        self,
        input_path: str,
        dzi_path: str,
        tiles_dir: str,
        tile_size: int,
        overlap: int,
        format: str,
        quality: int
    ):
        """使用 PIL 進行轉換 (適用於小檔案或沒有 vips 的環境)"""
        image = Image.open(input_path)
        
        # 如果是 RGBA 且輸出格式是 JPEG，需要轉換成 RGB
        if image.mode == 'RGBA' and format == 'jpeg':
            # 建立白色背景並合成
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # 使用 alpha 通道作為遮罩
            image = background
        elif image.mode != 'RGB' and format == 'jpeg':
            image = image.convert('RGB')
        
        width, height = image.size
        
        # 計算層級數
        max_level = math.ceil(math.log2(max(width, height)))
        
        # 生成 DZI XML
        dzi_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       Format="{format}"
       Overlap="{overlap}"
       TileSize="{tile_size}">
    <Size Width="{width}" Height="{height}"/>
</Image>'''
        
        with open(dzi_path, 'w') as f:
            f.write(dzi_content)
        
        # 生成各層級瓦片
        Path(tiles_dir).mkdir(parents=True, exist_ok=True)
        
        for level in range(max_level + 1):
            level_dir = os.path.join(tiles_dir, str(level))
            Path(level_dir).mkdir(exist_ok=True)
            
            # 計算該層級的尺寸
            scale = 2 ** (max_level - level)
            level_width = math.ceil(width / scale)
            level_height = math.ceil(height / scale)
            
            # 縮放圖片
            level_image = image.resize(
                (level_width, level_height),
                Image.Resampling.LANCZOS
            )
            
            # 切分瓦片
            cols = math.ceil(level_width / tile_size)
            rows = math.ceil(level_height / tile_size)
            
            for col in range(cols):
                for row in range(rows):
                    # 計算瓦片邊界
                    x = col * tile_size
                    y = row * tile_size
                    x2 = min(x + tile_size + overlap, level_width)
                    y2 = min(y + tile_size + overlap, level_height)
                    
                    # 裁切瓦片
                    tile = level_image.crop((x, y, x2, y2))
                    
                    # 儲存瓦片
                    tile_path = os.path.join(level_dir, f"{col}_{row}.{format}")
                    if format == "jpeg":
                        tile.save(tile_path, "JPEG", quality=quality)
                    else:
                        tile.save(tile_path, format.upper())
        
        print(f"DZI created with PIL: {dzi_path}")
    
    def _create_thumbnail(
        self,
        input_path: str,
        output_path: str,
        max_size: int = 256
    ):
        """生成縮圖"""
        try:
            if self.use_vips:
                if pyvips is None:
                    raise RuntimeError("pyvips is not available. Please install libvips.")
                image = pyvips.Image.thumbnail(input_path, max_size)
                image.write_to_file(output_path)
            else:
                image = Image.open(input_path)
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # 如果是 RGBA，轉換成 RGB 以便儲存為 JPEG
                if image.mode == 'RGBA':
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[3])
                    image = background
                elif image.mode != 'RGB':
                    image = image.convert('RGB')
                
                image.save(output_path, "JPEG", quality=85)
            
            print(f"Thumbnail created: {output_path}")
        except Exception as e:
            print(f"Failed to create thumbnail: {e}")


# 測試
if __name__ == "__main__":
    converter = DZIConverter()
    
    # 測試轉換
    test_image = "test.jpg"
    if os.path.exists(test_image):
        dzi_path, thumb_path = converter.convert(
            input_path=test_image,
            output_dir="./test_output"
        )
        print(f"DZI: {dzi_path}")
        print(f"Thumbnail: {thumb_path}")

