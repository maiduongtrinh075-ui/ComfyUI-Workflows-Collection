#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller 打包脚本
将 ComfyUI 工作流工具打包成 Windows 可执行文件
"""

import subprocess
import sys
from pathlib import Path

from paths import PROJECT_ROOT

def build_exe():
    """编译打包GUI为exe"""
    print("=" * 60)
    print("ComfyUI 工作流工具 - 打包脚本")
    print("=" * 60)

    # 检查PyInstaller
    print("\n[1] 检查PyInstaller...")
    try:
        import PyInstaller
        print("  PyInstaller已安装")
    except ImportError:
        print("  安装PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 打包命令
    print("\n[2] 开始打包...")

    gui_script = PROJECT_ROOT / "comfyui_tool_gui.py"
    output_dir = PROJECT_ROOT / "dist"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=ComfyUI工具",
        "--onefile",  # 打包成单个exe
        "--windowed",  # 不显示命令行窗口
        "--clean",
        "--noconfirm",
        f"--distpath={output_dir}",
        f"--workpath={output_dir}/build",
        str(gui_script)
    ]

    print(f"  命令: {' '.join(cmd)}")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe_path = output_dir / "ComfyUI工具.exe"
        print("\n" + "=" * 60)
        print("打包成功!")
        print(f"输出文件: {exe_path}")
        print("=" * 60)

        # 创建配置说明
        readme_path = output_dir / "使用说明.txt"
        readme_content = """
ComfyUI 工作流工具 使用说明

首次运行：
1. 双击 ComfyUI工具.exe 启动程序
2. 点击"添加微信路径"或"添加QQ路径"自动添加缓存目录
3. 或点击"添加路径"手动选择扫描目录
4. 设置输出目录（默认为项目目录下的 Extracted_ComfyUI_Assets）
5. 点击"保存配置"

使用方法：
1. 点击"扫描工作流"扫描缓存目录中的工作流文件
2. 点击"提取模型"获取模型资源列表和Civitai下载链接
3. 点击"媒体工作流"从图片/视频提取嵌入的工作流JSON
4. 点击"统计分析"生成工作流分析报告
5. 点击"缺失模型"检测本地缺少的模型
6. 点击"导入数据库"将数据导入SQLite数据库
7. 点击"导出报告"生成HTML和CSV报告

快捷操作：
- 点击"全部执行"一键完成所有流程
- 点击"Web界面"启动浏览器查看工作流
- 点击"终止任务"停止当前运行的任务
- 点击"清空输出目录"删除所有已提取的文件

配置文件：
- 配置自动保存到 gui_config.json
- 下次启动会自动加载上次配置

输出文件：
- 工作流JSON: Workflows_JSON/
- 媒体文件: Workflows_Media/
- 模型列表: model_resources.csv
- 统计报告: workflow_stats_report.html
- 缺失模型: missing_models_report.html
- 综合报告: comprehensive_report.html
- 数据库: comfyui_workflows.db

注意事项：
1. 首次扫描可能需要较长时间（取决于缓存文件数量）
2. 提取模型资源需要配置代理（默认127.0.0.1:7890）
3. 视频工作流提取需要安装FFmpeg
4. Web界面启动后访问 http://localhost:8080
5. 终止任务后可能需要等待当前操作完成

常见问题：
Q: 扫描结果为空？
A: 检查扫描路径是否正确，确保有权限访问微信/QQ缓存目录

Q: 模型提取失败？
A: 检查代理配置，确保可以访问Civitai API

Q: 视频工作流提取失败？
A: 安装FFmpeg并添加到系统PATH
"""
        readme_path.write_text(readme_content, encoding='utf-8')
        print(f"使用说明: {readme_path}")

    else:
        print("\n打包失败!")
        print(f"错误码: {result.returncode}")


if __name__ == "__main__":
    build_exe()