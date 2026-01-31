"""
簡化版 libvips 下載和設置腳本
直接使用已知的下載連結
"""

import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path

# 使用 build-win64-mxe repository 的最新版本
def get_download_url():
    """獲取最新的下載連結"""
    try:
        import json
        url = "https://api.github.com/repos/libvips/build-win64-mxe/releases/latest"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
            # 優先使用 web 版本（較小）
            assets = [a for a in data['assets'] 
                     if 'vips-dev-w64-web' in a['name'] and a['name'].endswith('.zip')]
            if assets:
                # 優先選擇 static 版本（包含所有依賴）
                static_assets = [a for a in assets if 'static' in a['name']]
                if static_assets:
                    return static_assets[0]['browser_download_url'], static_assets[0]['name']
                return assets[0]['browser_download_url'], assets[0]['name']
    except Exception as e:
        print(f"無法獲取最新版本: {e}")
    
    # 備用：使用已知版本
    return "https://github.com/libvips/build-win64-mxe/releases/download/v8.18.0/vips-dev-w64-web-8.18.0-static.zip", "vips-dev-w64-web-8.18.0-static.zip"

def download_with_progress(url, filepath):
    """下載檔案並顯示進度"""
    print(f"正在下載 libvips...")
    print(f"來源: {url}")
    print(f"目標: {filepath}")
    print("這可能需要幾分鐘，請稍候...\n")
    
    try:
        def progress_hook(count, block_size, total_size):
            percent = min(count * block_size * 100 / total_size, 100)
            bar_length = 40
            filled = int(bar_length * percent / 100)
            bar = '=' * filled + '-' * (bar_length - filled)
            print(f'\r[{bar}] {percent:.1f}%', end='', flush=True)
        
        urllib.request.urlretrieve(url, filepath, progress_hook)
        print("\n下載完成！")
        return True
    except Exception as e:
        print(f"\n下載失敗: {e}")
        print("\n請手動下載：")
        print(f"1. 前往: {url}")
        print("2. 下載檔案並解壓縮到 C:\\vips-dev-8.15.0\\")
        return False

def main():
    print("=" * 60)
    print("libvips Windows 自動下載和安裝")
    print("=" * 60)
    print()
    
    # 檢查是否已安裝
    try:
        if 'pyvips' in sys.modules:
            del sys.modules['pyvips']
        import pyvips
        img = pyvips.Image.black(1, 1)
        version = pyvips.version(0)
        print(f"[OK] libvips 已安裝並可用！")
        print(f"版本: {version}")
        return 0
    except:
        pass
    
    # 安裝位置
    install_dir = Path(r"C:\vips-dev-8.15.0")
    
    # 檢查是否已存在
    if (install_dir / "bin" / "libvips-42.dll").exists():
        print(f"[OK] libvips 已存在於: {install_dir}")
        print("正在設置環境變數...")
        os.environ['VIPSHOME'] = str(install_dir)
        os.environ['PATH'] = str(install_dir / "bin") + ';' + os.environ['PATH']
        
        # 測試
        try:
            if 'pyvips' in sys.modules:
                del sys.modules['pyvips']
            import pyvips
            img = pyvips.Image.black(1, 1)
            print("[OK] libvips 設置成功！")
            return 0
        except:
            pass
    
    # 獲取下載連結
    download_url, filename = get_download_url()
    print(f"將下載: {filename}")
    print()
    
    # 下載
    temp_dir = Path("./temp_libvips")
    temp_dir.mkdir(exist_ok=True)
    zip_path = temp_dir / filename
    
    if not zip_path.exists():
        if not download_with_progress(download_url, zip_path):
            return 1
    else:
        print(f"使用已下載的檔案: {zip_path}")
    
    # 解壓縮
    print("\n正在解壓縮...")
    extract_to = temp_dir / "extracted"
    extract_to.mkdir(exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print("解壓縮完成")
    except Exception as e:
        print(f"解壓縮失敗: {e}")
        return 1
    
    # 找到解壓縮後的資料夾
    extracted_folders = [f for f in extract_to.iterdir() if f.is_dir() and 'vips' in f.name.lower()]
    if not extracted_folders:
        print("[X] 無法找到解壓縮後的資料夾")
        return 1
    
    extracted_folder = extracted_folders[0]
    
    # 移動到目標位置
    print(f"\n正在安裝到: {install_dir}")
    if install_dir.exists():
        print("目標目錄已存在，正在刪除...")
        shutil.rmtree(install_dir)
    
    shutil.move(str(extracted_folder), str(install_dir))
    print(f"[OK] 安裝完成: {install_dir}")
    
    # 清理
    try:
        shutil.rmtree(temp_dir)
        print("已清理暫存檔案")
    except:
        pass
    
    # 設置環境變數
    print("\n正在設置環境變數...")
    os.environ['VIPSHOME'] = str(install_dir)
    os.environ['PATH'] = str(install_dir / "bin") + ';' + os.environ['PATH']
    
    # 更新 .env 檔案
    env_file = Path('.env')
    env_content = ""
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            env_content = f.read()
    
    if 'VIPSHOME' not in env_content:
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'\n# libvips Configuration\nVIPSHOME={install_dir}\n'
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_content)
        print("[OK] 已更新 .env 檔案")
    
    # 測試
    print("\n正在測試 libvips...")
    try:
        if 'pyvips' in sys.modules:
            del sys.modules['pyvips']
        import pyvips
        img = pyvips.Image.black(1, 1)
        version = pyvips.version(0)
        print(f"[OK] libvips 測試成功！")
        print(f"版本: {version}")
        
        print("\n" + "=" * 60)
        print("安裝完成！現在可以處理 SVS 檔案了。")
        print("=" * 60)
        print("\n請重新啟動應用程式以使設置完全生效。")
        return 0
    except Exception as e:
        print(f"[X] 測試失敗: {e}")
        print("\n但檔案已安裝，請重新啟動終端機後再試。")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已取消。")
        sys.exit(1)
