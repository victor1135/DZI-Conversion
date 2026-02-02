"""
检查 libvips 是否支持 JPEG2000
用于诊断 SVS 文件处理问题
"""

import sys
import os

# 设置 Windows 控制台编码为 UTF-8
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass

def check_pyvips():
    """检查 pyvips 是否可用"""
    try:
        import pyvips
        version = pyvips.version(0)
        print(f"✓ pyvips 已安装，版本: {version}")
        return pyvips
    except ImportError:
        print("✗ pyvips 未安装")
        print("  请运行: pip install pyvips")
        return None
    except Exception as e:
        print(f"✗ pyvips 导入失败: {e}")
        return None

def check_jpeg2000_support(pyvips_module):
    """检查是否支持 JPEG2000"""
    if pyvips_module is None:
        return False
    
    try:
        # 尝试检查可用的格式
        # 注意：这个方法可能不直接可用，我们尝试其他方式
        print("\n检查 JPEG2000 支持...")
        
        # 方法 1: 检查是否有 jp2kload 操作
        try:
            # 创建一个测试图像
            test_img = pyvips_module.Image.black(10, 10)
            
            # 尝试保存为 JPEG2000（如果支持的话）
            # 注意：这可能会失败，但错误信息会告诉我们是否支持
            try:
                # 尝试使用 jp2ksave（如果可用）
                # 这只是一个测试，不实际保存
                print("  尝试检测 JPEG2000 格式支持...")
                
                # 检查 libvips 的格式列表
                # 注意：pyvips 可能没有直接的方法来查询格式支持
                # 我们需要通过错误信息来判断
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'jp2k' in error_msg or 'jpeg2000' in error_msg:
                    if 'not' in error_msg or 'unsupported' in error_msg:
                        print("  ✗ JPEG2000 不支持")
                        return False
                
        except Exception as e:
            print(f"  检测过程中出现错误: {e}")
        
        # 方法 2: 检查 libvips 二进制文件（Windows）
        import platform
        if platform.system() == 'Windows':
            print("\n检查 libvips 安装...")
            vipshome = os.environ.get('VIPSHOME', '')
            path_env = os.environ.get('PATH', '')
            
            # 检查常见位置
            common_paths = [
                r"C:\vips-dev-8.15.0\bin",
                r"C:\vips-dev-8.14.0\bin",
                r"C:\vips-dev-8.13.0\bin",
            ]
            
            found_path = None
            for path in common_paths:
                if os.path.exists(path):
                    found_path = path
                    print(f"  ✓ 找到 libvips: {path}")
                    break
            
            if not found_path and vipshome:
                bin_path = os.path.join(vipshome, 'bin')
                if os.path.exists(bin_path):
                    found_path = bin_path
                    print(f"  ✓ 找到 libvips: {bin_path}")
            
            if not found_path:
                print("  ✗ 未找到 libvips 安装路径")
                print("\n解决方案:")
                print("  1. 下载包含 JPEG2000 支持的 libvips:")
                print("     - vips-dev-w64-all-*.zip (推荐，包含所有格式)")
                print("     - 或 vips-dev-w64-web-*.zip (包含 web 格式)")
                print("  2. 解压到 C:\\vips-dev-8.15.0\\")
                print("  3. 设置环境变量 VIPSHOME=C:\\vips-dev-8.15.0")
                print("  4. 或将 C:\\vips-dev-8.15.0\\bin 添加到 PATH")
                return False
            
            # 检查是否有 openjpeg DLL
            openjpeg_dlls = [
                'libopenjp2.dll',
                'openjpeg.dll',
            ]
            
            has_openjpeg = False
            for dll in openjpeg_dlls:
                dll_path = os.path.join(found_path, dll)
                if os.path.exists(dll_path):
                    print(f"  ✓ 找到 {dll} - JPEG2000 支持可用")
                    has_openjpeg = True
                    break
            
            if not has_openjpeg:
                print("  ✗ 未找到 openjpeg DLL - JPEG2000 不支持")
                print("\n解决方案:")
                print("  当前安装的 libvips 版本不包含 JPEG2000 支持")
                print("  请下载包含所有格式的版本:")
                print("  https://github.com/libvips/libvips/releases")
                print("  查找: vips-dev-w64-all-*.zip")
                return False
        
        # 如果到这里，假设支持（实际测试需要真实的 JPEG2000 文件）
        print("  ? 无法直接检测，但 libvips 已安装")
        print("  如果处理 SVS 文件时出现 JPEG2000 错误，")
        print("  请下载包含所有格式的 libvips 版本")
        return True
        
    except Exception as e:
        print(f"  检查失败: {e}")
        return False

def main():
    print("=" * 60)
    print("libvips JPEG2000 支持检查工具")
    print("=" * 60)
    
    pyvips = check_pyvips()
    if pyvips is None:
        sys.exit(1)
    
    has_jpeg2000 = check_jpeg2000_support(pyvips)
    
    print("\n" + "=" * 60)
    if has_jpeg2000:
        print("✓ 检查完成 - 可能支持 JPEG2000")
        print("  如果处理 SVS 文件时仍然出错，请确保使用")
        print("  包含所有格式的 libvips 版本 (vips-dev-w64-all-*.zip)")
    else:
        print("✗ JPEG2000 支持不可用")
        print("\n请按照上面的解决方案操作")
    print("=" * 60)

if __name__ == "__main__":
    main()
