"""
自動下載並設置 libvips for Windows
"""

import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path

def get_latest_release_info():
    """獲取最新版本資訊"""
    try:
        import json
        url = "https://api.github.com/repos/libvips/libvips/releases/latest"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read())
            tag = data['tag_name']
            # 尋找 Windows 版本
            assets = [a for a in data['assets'] 
                     if 'vips-dev-w64-web' in a['name'] and a['name'].endswith('.zip')]
            if assets:
                return tag, assets[0]['browser_download_url'], assets[0]['name']
    except Exception as e:
        print(f"無法獲取最新版本資訊: {e}")
    
    # 備用：使用已知的穩定版本
    return "v8.15.0", None, "vips-dev-w64-web-8.15.0.zip"

def download_file(url, filename, target_dir):
    """下載檔案"""
    filepath = os.path.join(target_dir, filename)
    
    if os.path.exists(filepath):
        print(f"檔案已存在: {filepath}")
        return filepath
    
    print(f"正在下載: {filename}")
    print(f"這可能需要幾分鐘，請稍候...")
    
    try:
        def show_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100)
            print(f"\r進度: {percent:.1f}%", end='', flush=True)
        
        urllib.request.urlretrieve(url, filepath, show_progress)
        print()  # 換行
        print(f"下載完成: {filepath}")
        return filepath
    except Exception as e:
        print(f"\n下載失敗: {e}")
        return None

def extract_zip(zip_path, extract_to):
    """解壓縮 ZIP 檔案"""
    print(f"正在解壓縮到: {extract_to}")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        print("解壓縮完成")
        return True
    except Exception as e:
        print(f"解壓縮失敗: {e}")
        return False

def find_extracted_folder(base_dir):
    """找到解壓縮後的資料夾"""
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and 'vips' in item.lower():
            bin_path = os.path.join(item_path, 'bin')
            dll_file = os.path.join(bin_path, 'libvips-42.dll')
            if os.path.exists(dll_file):
                return item_path
    return None

def setup_environment(vips_path):
    """設置環境變數"""
    bin_path = os.path.join(vips_path, 'bin')
    
    # 設置當前會話的環境變數
    os.environ['VIPSHOME'] = vips_path
    os.environ['PATH'] = bin_path + ';' + os.environ['PATH']
    
    print(f"\n[OK] 環境變數已設置（當前會話）")
    print(f"VIPSHOME = {vips_path}")
    print(f"PATH 已包含: {bin_path}")
    
    # 測試
    try:
        if 'pyvips' in sys.modules:
            del sys.modules['pyvips']
        import pyvips
        img = pyvips.Image.black(1, 1)
        version = pyvips.version(0)
        print(f"\n[OK] libvips 測試成功！")
        print(f"版本: {version}")
        return True
    except Exception as e:
        print(f"\n[X] 測試失敗: {e}")
        return False

def create_env_file(vips_path):
    """創建或更新 .env 檔案"""
    env_file = Path('.env')
    env_content = ""
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            env_content = f.read()
    
    # 檢查是否已有 VIPSHOME
    if 'VIPSHOME' in env_content:
        # 更新現有的 VIPSHOME
        lines = env_content.split('\n')
        new_lines = []
        for line in lines:
            if line.startswith('VIPSHOME='):
                new_lines.append(f'VIPSHOME={vips_path}')
            else:
                new_lines.append(line)
        env_content = '\n'.join(new_lines)
    else:
        # 添加 VIPSHOME
        if env_content and not env_content.endswith('\n'):
            env_content += '\n'
        env_content += f'\n# libvips Configuration\nVIPSHOME={vips_path}\n'
    
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"\n[OK] 已更新 .env 檔案")

def main():
    print("=" * 60)
    print("libvips Windows 自動安裝工具")
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
        print("\n無需重新安裝。")
        return 0
    except:
        pass
    
    # 獲取版本資訊
    tag, download_url, filename = get_latest_release_info()
    print(f"最新版本: {tag}")
    
    if not download_url:
        print("\n無法自動下載，請手動下載：")
        print("1. 前往: https://github.com/libvips/libvips/releases")
        print(f"2. 下載: {filename}")
        print("3. 解壓縮到: C:\\vips-dev-8.15.0\\")
        print("4. 運行: python setup_libvips_path.py")
        return 1
    
    print(f"下載連結: {download_url}")
    print()
    
    # 選擇安裝位置
    install_dir = input("請輸入安裝目錄（直接按 Enter 使用 C:\\vips-dev-8.15.0）: ").strip()
    if not install_dir:
        install_dir = r"C:\vips-dev-8.15.0"
    
    install_path = Path(install_dir)
    
    # 檢查是否已存在
    bin_path = install_path / "bin"
    dll_file = bin_path / "libvips-42.dll"
    if dll_file.exists():
        print(f"\n[OK] libvips 已存在於: {install_path}")
        if setup_environment(str(install_path)):
            create_env_file(str(install_path))
            return 0
    
    # 下載
    temp_dir = Path("./temp_libvips")
    temp_dir.mkdir(exist_ok=True)
    
    zip_path = download_file(download_url, filename, temp_dir)
    if not zip_path:
        return 1
    
    # 解壓縮
    extract_base = temp_dir / "extracted"
    extract_base.mkdir(exist_ok=True)
    
    if not extract_zip(zip_path, extract_base):
        return 1
    
    # 找到解壓縮後的資料夾
    extracted_folder = find_extracted_folder(extract_base)
    if not extracted_folder:
        print("[X] 無法找到解壓縮後的 libvips 資料夾")
        return 1
    
    # 移動到目標位置
    print(f"\n正在移動到: {install_path}")
    if install_path.exists():
        shutil.rmtree(install_path)
    shutil.move(extracted_folder, install_path)
    print(f"[OK] 已移動到: {install_path}")
    
    # 清理暫存檔案
    try:
        shutil.rmtree(temp_dir)
    except:
        pass
    
    # 設置環境變數
    if setup_environment(str(install_path)):
        create_env_file(str(install_path))
        print("\n" + "=" * 60)
        print("安裝完成！")
        print("=" * 60)
        print("\n請重新啟動應用程式以使設置生效。")
        return 0
    else:
        print("\n安裝完成，但測試失敗。")
        print("請手動檢查安裝是否正確。")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已取消安裝。")
        sys.exit(1)
