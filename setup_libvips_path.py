"""
快速設置 libvips 路徑的輔助腳本
如果 libvips 已下載但未設置環境變數，可以運行此腳本
"""

import os
import sys

def setup_libvips_path():
    """設置 libvips 路徑"""
    print("=" * 60)
    print("libvips 路徑設置工具")
    print("=" * 60)
    print()
    
    # 常見位置
    common_paths = [
        r"C:\vips-dev-8.15.0",
        r"C:\vips-dev-8.14.0",
        r"C:\vips-dev-8.13.0",
        r"D:\vips-dev-8.15.0",
        r"D:\libs\vips-dev-8.15.0",
    ]
    
    print("正在搜尋 libvips...")
    found_paths = []
    
    for base_path in common_paths:
        bin_path = os.path.join(base_path, "bin")
        dll_file = os.path.join(bin_path, "libvips-42.dll")
        if os.path.exists(dll_file):
            found_paths.append(base_path)
            print(f"[OK] 找到: {base_path}")
    
    if not found_paths:
        print("[X] 未找到 libvips")
        print()
        print("請先下載並解壓縮 libvips:")
        print("1. 前往: https://github.com/libvips/libvips/releases")
        print("2. 下載: vips-dev-w64-web-*.zip")
        print("3. 解壓縮到: C:\\vips-dev-8.15.0\\")
        return False
    
    # 如果找到多個，使用第一個
    selected_path = found_paths[0]
    bin_path = os.path.join(selected_path, "bin")
    
    print()
    print(f"使用路徑: {selected_path}")
    print()
    
    # 設置環境變數
    os.environ['VIPSHOME'] = selected_path
    os.environ['PATH'] = bin_path + ';' + os.environ['PATH']
    
    # 測試
    try:
        if 'pyvips' in sys.modules:
            del sys.modules['pyvips']
        import pyvips
        img = pyvips.Image.black(1, 1)
        version = pyvips.version(0)
        print(f"[OK] libvips 設置成功！")
        print(f"版本: {version}")
        print()
        print("=" * 60)
        print("設置完成！現在可以在代碼中使用 pyvips 了。")
        print("=" * 60)
        print()
        print("注意：此設置僅在當前 Python 會話中有效。")
        print("要永久設置，請：")
        print("1. 設置系統環境變數 VIPSHOME =", selected_path)
        print("2. 或在代碼開頭添加：")
        print(f"   import os")
        print(f"   os.environ['VIPSHOME'] = r'{selected_path}'")
        return True
    except Exception as e:
        print(f"[X] 設置失敗: {e}")
        return False

if __name__ == "__main__":
    setup_libvips_path()
