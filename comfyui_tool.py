#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 工作流工具集 - 统一CLI入口
整合所有功能：扫描、模型提取、媒体工作流提取、去重
"""

import argparse
import sys
import os

from paths import PROJECT_ROOT, OUTPUT_DIR as DEFAULT_OUTPUT_DIR

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# subprocess 调用统一使用项目根作为工作目录
_CWD = str(PROJECT_ROOT)

def main():
    parser = argparse.ArgumentParser(
        description='ComfyUI 工作流工具集',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python comfyui_tool.py --scan          扫描微信/QQ缓存提取工作流
  python comfyui_tool.py --models         从工作流提取模型资源
  python comfyui_tool.py --media          从媒体文件提取工作流JSON
  python comfyui_tool.py --dedup          去重已提取的文件
  python comfyui_tool.py --stats          统计工作流分析报告
  python comfyui_tool.py --missing        检测缺失模型
  python comfyui_tool.py --web            启动Web可视化界面
  python comfyui_tool.py --database       导入数据到SQLite数据库
  python comfyui_tool.py --export         导出HTML/CSV报告
  python comfyui_tool.py --all            执行全部流程(不含Web)
        '''
    )

    parser.add_argument('--scan', action='store_true', help='扫描微信/QQ缓存提取工作流')
    parser.add_argument('--models', action='store_true', help='从工作流提取模型资源列表')
    parser.add_argument('--media', action='store_true', help='从媒体文件提取工作流JSON')
    parser.add_argument('--dedup', action='store_true', help='去重已提取的文件')
    parser.add_argument('--stats', action='store_true', help='生成工作流统计分析报告')
    parser.add_argument('--missing', action='store_true', help='检测缺失的模型')
    parser.add_argument('--web', action='store_true', help='启动Web可视化界面')
    parser.add_argument('--database', action='store_true', help='导入数据到SQLite数据库')
    parser.add_argument('--export', action='store_true', help='导出HTML/CSV报告')
    parser.add_argument('--all', action='store_true', help='执行全部流程(不含Web)')
    parser.add_argument('--qce', action='store_true', help='启动QCE (QQ聊天导出工具)')
    parser.add_argument('--qce-export', action='store_true', help='交互式导出QQ聊天记录')
    parser.add_argument('--proxy', type=str, default='http://127.0.0.1:7890', help='代理地址 (默认: 7890端口)')
    parser.add_argument('--output', type=str, default=str(DEFAULT_OUTPUT_DIR), help='输出目录')

    args = parser.parse_args()

    if not any([args.scan, args.models, args.media, args.dedup, args.stats, args.missing, args.web, args.database, args.export, args.all, args.qce, args.qce_export]):
        parser.print_help()
        return

    print("=" * 60)
    print("ComfyUI 工作流工具集")
    print("=" * 60)

    # 执行选定的任务
    if args.scan or args.all:
        print("\n[1] 执行工作流扫描...")
        run_scan()

    if args.models or args.all:
        print("\n[2] 提取模型资源...")
        run_models(args.proxy)

    if args.media or args.all:
        print("\n[3] 提取媒体工作流...")
        run_media()

    if args.dedup or args.all:
        print("\n[4] 执行去重...")
        run_dedup()

    if args.stats or args.all:
        print("\n[5] 生成统计分析...")
        run_stats()

    if args.missing or args.all:
        print("\n[6] 检测缺失模型...")
        run_missing()

    if args.web:
        print("\n[7] 启动Web可视化界面...")
        run_web()

    if args.database or args.all:
        print("\n[8] 导入数据库...")
        run_database()

    if args.export or args.all:
        print("\n[9] 导出报告...")
        run_export()

    if args.qce:
        print("\n[10] 启动 QCE...")
        run_qce()

    if args.qce_export:
        print("\n[11] 导出 QQ 聊天记录...")
        run_qce_export()

    print("\n" + "=" * 60)
    print("全部完成!")
    print("=" * 60)


def run_scan():
    """执行工作流扫描"""
    import subprocess
    result = subprocess.run([sys.executable, 'comfyui_extractor.py'], cwd=_CWD)
    if result.returncode != 0:
        print("扫描失败，请检查 comfyui_extractor.py")


def run_models(proxy):
    """提取模型资源"""
    import subprocess
    env = os.environ.copy()
    env['PROXY'] = proxy
    result = subprocess.run([sys.executable, 'extract_model_resources.py'], cwd=_CWD, env=env)
    if result.returncode != 0:
        print("模型提取失败")


def run_media():
    """提取媒体工作流"""
    import subprocess
    result = subprocess.run([sys.executable, 'extract_media_workflows.py'], cwd=_CWD)
    if result.returncode != 0:
        print("媒体工作流提取失败")


def run_dedup():
    """执行去重"""
    import subprocess
    result = subprocess.run([sys.executable, 'deduplicate_files.py'], cwd=_CWD)
    if result.returncode != 0:
        print("去重失败")


def run_stats():
    """生成统计分析报告"""
    import subprocess
    result = subprocess.run([sys.executable, 'workflow_stats.py'], cwd=_CWD)
    if result.returncode != 0:
        print("统计分析失败")


def run_missing():
    """检测缺失模型"""
    import subprocess
    result = subprocess.run([sys.executable, 'missing_model_detector.py'], cwd=_CWD)
    if result.returncode != 0:
        print("缺失模型检测失败")


def run_web():
    """启动Web可视化界面"""
    print("启动Web服务器...")
    print("地址: http://localhost:8080")
    print("按 Ctrl+C 停止服务器")
    import subprocess
    subprocess.run([sys.executable, 'web_visualizer.py'], cwd=_CWD)


def run_database():
    """导入数据库"""
    import subprocess
    result = subprocess.run([sys.executable, 'database_manager.py'], cwd=_CWD)
    if result.returncode != 0:
        print("数据库导入失败")


def run_export():
    """导出报告"""
    import subprocess
    result = subprocess.run([sys.executable, 'export_reports.py'], cwd=_CWD)
    if result.returncode != 0:
        print("报告导出失败")


def run_qce():
    """启动 QCE"""
    import subprocess
    subprocess.run([sys.executable, 'start_qce.py'], cwd=_CWD)


def run_qce_export():
    """交互式导出 QQ 聊天记录"""
    import subprocess
    subprocess.run([sys.executable, 'qce_api.py', '--export'], cwd=_CWD)


if __name__ == "__main__":
    main()