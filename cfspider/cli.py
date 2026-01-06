"""
CFspider 命令行工具
"""

import sys
import subprocess


def install_browser():
    """
    安装 Chromium 浏览器
    
    Example:
        >>> import cfspider
        >>> cfspider.install_browser()
    """
    try:
        # 使用 playwright 命令行安装
        result = subprocess.run(
            [sys.executable, '-m', 'playwright', 'install', 'chromium'],
            capture_output=False
        )
        return result.returncode == 0
    except Exception as e:
        print(f"安装失败: {e}")
        return False


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'install':
        print("正在安装 Chromium 浏览器...")
        if install_browser():
            print("安装完成!")
        else:
            print("安装失败，请检查网络连接或手动安装")
            sys.exit(1)
    
    elif command == 'version':
        from . import __version__
        print(f"cfspider {__version__}")
    
    elif command == 'help' or command == '-h' or command == '--help':
        print_help()
    
    else:
        print(f"未知命令: {command}")
        print_help()
        sys.exit(1)


def print_help():
    """打印帮助信息"""
    print("""
CFspider - Cloudflare 代理 IP 池

用法:
    cfspider <command>

命令:
    install     安装 Chromium 浏览器（用于 Browser 功能）
    version     显示版本号
    help        显示帮助信息

示例:
    cfspider install    # 安装浏览器
    cfspider version    # 显示版本

更多信息请访问: https://github.com/violettoolssite/CFspider
""")


if __name__ == '__main__':
    main()

