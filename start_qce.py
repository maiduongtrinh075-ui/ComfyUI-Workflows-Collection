#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QCE 一键启动脚本
启动 NapCat + QQ Chat Exporter 工具
"""

import subprocess
import sys
import time
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

QCE_DIR = Path(__file__).parent / 'qq-chat-exporter'
NAPI_LOADER = QCE_DIR / 'napiLoader.bat'

WEBUI_PORT = 6099
API_PORT = 40653


def main():
    print("=" * 60)
    print("QCE (QQ Chat Exporter) 启动工具")
    print("=" * 60)

    if not NAPI_LOADER.exists():
        print(f"错误: 未找到 QCE 工具")
        print(f"请确认目录存在: {QCE_DIR}")
        return

    print(f"\nQCE 目录: {QCE_DIR}")
    print(f"启动 napiLoader.bat...")

    # 启动 QCE
    process = subprocess.Popen(
        ['cmd', '/c', str(NAPI_LOADER)],
        cwd=str(QCE_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

    print(f"\n进程已启动 (PID: {process.pid})")
    print("\n" + "-" * 60)
    print("请等待 QQ 启动并登录...")
    print("-" * 60)

    # 等待用户确认
    input("\nQQ 登录完成后，按回车键继续...")

    print("\n" + "=" * 60)
    print("QCE 已就绪!")
    print("=" * 60)
    print(f"\nWeb UI 地址: http://localhost:{WEBUI_PORT}/qce-v4-tool")
    print(f"API 地址: http://localhost:{API_PORT}")
    print(f"\nToken: 在 %USERPROFILE%\\.qq-chat-exporter\\security.json 中查看")
    print("\n" + "-" * 60)
    print("使用方式:")
    print("  1. 浏览器打开 Web UI 地址导出聊天记录")
    print("  2. 运行 python qce_api.py --export 交互式导出")
    print("  3. 运行 python qce_api.py --list 查看聊天列表")
    print("-" * 60)

    print("\n提示: 关闭此窗口不会停止 QCE")
    print("      要停止 QCE，请关闭 QQ 或命令行窗口")

    input("\n按回车键退出此脚本...")


if __name__ == '__main__':
    main()