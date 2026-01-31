"""
Windows libvips 自動安裝輔助腳本
幫助下載並設置 libvips 環境變數
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil
from pathlib import Path

def check_pyvips_package():
    """檢查 pyvips Python 套件"""
    try:
        import pyvips
        return True
    except ImportError:
        return False
    except Exception:
        # 可能是系統庫未找到，但套件已安裝
        return True

def test_libvips():
    """測試 libvips 是否可用"""
    try:
        import pyvips
        img = pyvips.Image.black(1, 1)
        version = pyvips.version(0)
        print("[OK] libvips 系統庫已可用！")
        print(f"  版本: {version}")
        return True
    except ImportError:
        print("[X] pyvips Python 套件未安裝")
        return False
    except Exception as e:
        print("[X] libvips 系統庫未找到")
        print(f"  錯誤: {str(e)[:100]}")
        return False

def download_libvips():
    """檢查 libvips 狀態"""
    print("=" * 60)
    print("libvips Windows 安裝輔助工具")
    print("=" * 60)
    print()
    
    # 檢查 Python 套件
    if not check_pyvips_package():
        print("[X] pyvips Python 套件未安裝")
        print("  正在安裝 pyvips...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyvips"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[OK] pyvips 安裝完成")
        except Exception as e:
            print(f"[X] 安裝失敗: {e}")
            return False
    else:
        print("[OK] pyvips Python 套件已安裝")
    
    # 測試是否能載入
    return test_libvips()

def check_manual_install():
    """檢查手動安裝指引"""
    print("=" * 60)
    print("需要手動安裝 libvips 系統庫")
    print("=" * 60)
    print()
    print("請按照以下步驟操作：")
    print()
    print("1. 下載 libvips:")
    print("   前往: https://github.com/libvips/libvips/releases")
    print("   下載: vips-dev-w64-web-*.zip (最新版本)")
    print()
    print("2. 解壓縮到固定位置，例如:")
    print("   C:\\vips-dev-8.15.0\\")
    print()
    print("3. 設置環境變數:")
    print("   - 按 Win+R，輸入 sysdm.cpl")
    print("   - 進階 → 環境變數")
    print("   - 編輯 Path，新增: C:\\vips-dev-8.15.0\\bin")
    print("   - 重新啟動終端機")
    print()
    print("4. 或使用代碼設置（臨時）:")
    print("   在 dzi_converter.py 開頭添加:")
    print("   import os")
    print("   os.environ['PATH'] = r'C:\\vips-dev-8.15.0\\bin' + ';' + os.environ['PATH']")
    print()
    print("詳細說明請查看: INSTALL_LIBVIPS.md")
    print()

def try_find_libvips():
    """嘗試在常見位置找到 libvips"""
    common_paths = [
        r"C:\vips-dev-8.15.0\bin",
        r"C:\vips-dev-8.14.0\bin",
        r"C:\vips-dev-8.13.0\bin",
        r"D:\vips-dev-8.15.0\bin",
        r"D:\libs\vips-dev-8.15.0\bin",
    ]
    
    for path in common_paths:
        dll_path = Path(path) / "libvips-42.dll"
        if dll_path.exists():
            print(f"[OK] 找到 libvips: {path}")
            print(f"  正在設置環境變數...")
            os.environ['PATH'] = path + ';' + os.environ['PATH']
            
            # 測試（需要重新導入）
            try:
                # 清除已導入的模組
                if 'pyvips' in sys.modules:
                    del sys.modules['pyvips']
                import pyvips
                img = pyvips.Image.black(1, 1)
                print(f"[OK] libvips 設置成功！")
                print(f"  版本: {pyvips.version(0)}")
                return True
            except Exception as e:
                print(f"[X] 設置失敗: {e}")
    
    return False

if __name__ == "__main__":
    # 先測試是否已可用
    if download_libvips():
        print()
        print("=" * 60)
        print("安裝完成！現在可以處理 SVS 檔案了。")
        print("=" * 60)
        sys.exit(0)
    
    # 嘗試自動找到
    print()
    print("正在搜尋已安裝的 libvips...")
    if try_find_libvips():
        print()
        print("=" * 60)
        print("找到並設置成功！現在可以處理 SVS 檔案了。")
        print("=" * 60)
        print()
        print("注意：此設置僅在當前終端機有效。")
        print("要永久設置，請按照 INSTALL_LIBVIPS.md 的說明操作。")
        sys.exit(0)
    
    # 需要手動安裝
    print()
    check_manual_install()
    sys.exit(1)
