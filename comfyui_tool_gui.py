#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 工作流工具 - Windows 桌面版
带GUI界面，支持路径配置、进度显示、任务控制
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import sys
import os
import shutil
import json
from pathlib import Path
import queue

# 配置文件路径
CONFIG_FILE = Path("F:/ComfyuiCatchJson/gui_config.json")


class ComfyUIToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ComfyUI 工作流工具 v1.0")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # 配置数据
        self.scan_paths = []
        self.output_dir = "F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets"
        self.proxy = "http://127.0.0.1:7890"

        # 任务控制
        self.current_process = None
        self.is_running = False
        self.log_queue = queue.Queue()

        # 加载配置
        self.load_config()

        # 创建界面
        self.create_widgets()

        # 启动日志更新
        self.update_log_display()

    def load_config(self):
        """加载配置文件"""
        if CONFIG_FILE.exists():
            try:
                config = json.load(open(CONFIG_FILE, encoding='utf-8'))
                self.scan_paths = config.get('scan_paths', [])
                self.output_dir = config.get('output_dir', self.output_dir)
                self.proxy = config.get('proxy', self.proxy)
            except:
                pass

    def save_config(self):
        """保存配置文件"""
        config = {
            'scan_paths': self.scan_paths,
            'output_dir': self.output_dir,
            'proxy': self.proxy
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 扫描路径配置 =====
        path_frame = ttk.LabelFrame(main_frame, text="扫描路径配置", padding="10")
        path_frame.pack(fill=tk.X, pady=5)

        # 路径列表
        self.path_listbox = tk.Listbox(path_frame, height=4, selectmode=tk.EXTENDED)
        self.path_listbox.pack(fill=tk.X, pady=5)
        for path in self.scan_paths:
            self.path_listbox.insert(tk.END, path)

        # 路径按钮
        path_btn_frame = ttk.Frame(path_frame)
        path_btn_frame.pack(fill=tk.X)

        ttk.Button(path_btn_frame, text="添加路径", command=self.add_scan_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(path_btn_frame, text="添加微信路径", command=self.add_wechat_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(path_btn_frame, text="添加QQ路径", command=self.add_qq_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(path_btn_frame, text="删除选中", command=self.remove_scan_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(path_btn_frame, text="清空列表", command=self.clear_scan_paths).pack(side=tk.LEFT, padx=5)

        # ===== 输出目录配置 =====
        output_frame = ttk.LabelFrame(main_frame, text="输出目录配置", padding="10")
        output_frame.pack(fill=tk.X, pady=5)

        output_row = ttk.Frame(output_frame)
        output_row.pack(fill=tk.X)

        ttk.Label(output_row, text="输出目录:").pack(side=tk.LEFT)
        self.output_entry = ttk.Entry(output_row, width=50)
        self.output_entry.insert(0, self.output_dir)
        self.output_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_row, text="选择目录", command=self.select_output_dir).pack(side=tk.LEFT)

        # ===== 其他配置 =====
        config_frame = ttk.LabelFrame(main_frame, text="其他配置", padding="10")
        config_frame.pack(fill=tk.X, pady=5)

        proxy_row = ttk.Frame(config_frame)
        proxy_row.pack(fill=tk.X)

        ttk.Label(proxy_row, text="代理地址:").pack(side=tk.LEFT)
        self.proxy_entry = ttk.Entry(proxy_row, width=30)
        self.proxy_entry.insert(0, self.proxy)
        self.proxy_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(proxy_row, text="(用于Civitai API访问)").pack(side=tk.LEFT)

        # ===== 功能按钮 =====
        func_frame = ttk.LabelFrame(main_frame, text="功能操作", padding="10")
        func_frame.pack(fill=tk.X, pady=5)

        # 第一行按钮
        btn_row1 = ttk.Frame(func_frame)
        btn_row1.pack(fill=tk.X, pady=3)

        self.btn_scan = ttk.Button(btn_row1, text="🔍 扫描工作流", command=self.run_scan, width=15)
        self.btn_scan.pack(side=tk.LEFT, padx=5)

        self.btn_models = ttk.Button(btn_row1, text="📦 提取模型", command=self.run_models, width=15)
        self.btn_models.pack(side=tk.LEFT, padx=5)

        self.btn_media = ttk.Button(btn_row1, text="📸 媒体工作流", command=self.run_media, width=15)
        self.btn_media.pack(side=tk.LEFT, padx=5)

        self.btn_stats = ttk.Button(btn_row1, text="📊 统计分析", command=self.run_stats, width=15)
        self.btn_stats.pack(side=tk.LEFT, padx=5)

        # 第二行按钮
        btn_row2 = ttk.Frame(func_frame)
        btn_row2.pack(fill=tk.X, pady=3)

        self.btn_missing = ttk.Button(btn_row2, text="⚠️ 缺失模型", command=self.run_missing, width=15)
        self.btn_missing.pack(side=tk.LEFT, padx=5)

        self.btn_database = ttk.Button(btn_row2, text="💾 导入数据库", command=self.run_database, width=15)
        self.btn_database.pack(side=tk.LEFT, padx=5)

        self.btn_export = ttk.Button(btn_row2, text="📋 导出报告", command=self.run_export, width=15)
        self.btn_export.pack(side=tk.LEFT, padx=5)

        self.btn_web = ttk.Button(btn_row2, text="🌐 Web界面", command=self.run_web, width=15)
        self.btn_web.pack(side=tk.LEFT, padx=5)

        # 第三行 - 全部执行
        btn_row3 = ttk.Frame(func_frame)
        btn_row3.pack(fill=tk.X, pady=3)

        self.btn_all = ttk.Button(btn_row3, text="⚡ 全部执行", command=self.run_all, width=20)
        self.btn_all.pack(side=tk.LEFT, padx=5)

        # ===== 控制按钮 =====
        ctrl_frame = ttk.Frame(func_frame)
        ctrl_frame.pack(fill=tk.X, pady=5)

        self.btn_stop = ttk.Button(ctrl_frame, text="⏹️ 终止任务", command=self.stop_task, width=15)
        self.btn_stop.pack(side=tk.LEFT, padx=5)
        self.btn_stop.config(state=tk.DISABLED)

        self.btn_clear_output = ttk.Button(ctrl_frame, text="🗑️ 清空输出目录", command=self.clear_output_dir, width=15)
        self.btn_clear_output.pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="💾 保存配置", command=self.save_config_click, width=15).pack(side=tk.LEFT, padx=5)

        # ===== 进度显示 =====
        progress_frame = ttk.LabelFrame(main_frame, text="进度", padding="10")
        progress_frame.pack(fill=tk.X, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X)

        self.status_label = ttk.Label(progress_frame, text="状态: 就绪")
        self.status_label.pack(fill=tk.X)

        # ===== 统计信息 =====
        stats_frame = ttk.LabelFrame(main_frame, text="统计信息", padding="10")
        stats_frame.pack(fill=tk.X, pady=5)

        stats_row = ttk.Frame(stats_frame)
        stats_row.pack(fill=tk.X)

        self.stats_workflows = ttk.Label(stats_row, text="工作流: 0")
        self.stats_workflows.pack(side=tk.LEFT, padx=10)

        self.stats_models = ttk.Label(stats_row, text="模型: 0")
        self.stats_models.pack(side=tk.LEFT, padx=10)

        self.stats_media = ttk.Label(stats_row, text="媒体: 0")
        self.stats_media.pack(side=tk.LEFT, padx=10)

        self.stats_nodes = ttk.Label(stats_row, text="节点: 0")
        self.stats_nodes.pack(side=tk.LEFT, padx=10)

        ttk.Button(stats_row, text="刷新统计", command=self.refresh_stats).pack(side=tk.LEFT, padx=10)

        # ===== 日志显示 =====
        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 配置日志颜色
        self.log_text.tag_config('info', foreground='black')
        self.log_text.tag_config('success', foreground='green')
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('warning', foreground='orange')

        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X)

        ttk.Button(log_btn_frame, text="清空日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_btn_frame, text="保存日志", command=self.save_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(log_btn_frame, text="打开输出目录", command=self.open_output_dir).pack(side=tk.LEFT, padx=5)

        # 初始化统计
        self.refresh_stats()

    def add_scan_path(self):
        """添加扫描路径"""
        path = filedialog.askdirectory(title="选择扫描目录")
        if path:
            self.scan_paths.append(path)
            self.path_listbox.insert(tk.END, path)
            self.save_config()

    def add_wechat_path(self):
        """添加微信缓存路径"""
        username = os.environ.get('USERNAME', '')
        wechat_paths = [
            f"C:/Users/{username}/Documents/WeChat Files",
            f"C:/Users/{username}/xwechat_files",
        ]
        for path in wechat_paths:
            if Path(path).exists() and path not in self.scan_paths:
                self.scan_paths.append(path)
                self.path_listbox.insert(tk.END, path)
        self.save_config()

    def add_qq_path(self):
        """添加QQ缓存路径"""
        username = os.environ.get('USERNAME', '')
        qq_paths = [
            f"C:/Users/{username}/Documents/Tencent Files",
            f"C:/Users/{username}/Tencent",
        ]
        for path in qq_paths:
            if Path(path).exists() and path not in self.scan_paths:
                self.scan_paths.append(path)
                self.path_listbox.insert(tk.END, path)
        self.save_config()

    def remove_scan_path(self):
        """删除选中的扫描路径"""
        selected = self.path_listbox.curselection()
        for idx in selected[::-1]:
            self.path_listbox.delete(idx)
            self.scan_paths.pop(idx)
        self.save_config()

    def clear_scan_paths(self):
        """清空扫描路径列表"""
        self.path_listbox.delete(0, tk.END)
        self.scan_paths = []
        self.save_config()

    def select_output_dir(self):
        """选择输出目录"""
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)
            self.output_dir = path
            self.save_config()

    def save_config_click(self):
        """保存配置按钮"""
        self.output_dir = self.output_entry.get()
        self.proxy = self.proxy_entry.get()
        self.save_config()
        self.log("配置已保存", 'success')

    def log(self, message, tag='info'):
        """添加日志"""
        self.log_queue.put((message, tag))

    def update_log_display(self):
        """更新日志显示"""
        try:
            while True:
                message, tag = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, message + '\n', tag)
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.update_log_display)

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)

    def save_log(self):
        """保存日志到文件"""
        log_content = self.log_text.get(1.0, tk.END)
        log_file = Path(self.output_dir) / "gui_log.txt"
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(log_content)
        messagebox.showinfo("保存成功", f"日志已保存到: {log_file}")

    def open_output_dir(self):
        """打开输出目录"""
        output_path = Path(self.output_dir)
        if output_path.exists():
            os.startfile(str(output_path))
        else:
            messagebox.showwarning("目录不存在", "输出目录尚未创建")

    def refresh_stats(self):
        """刷新统计信息"""
        output_path = Path(self.output_dir)

        # 工作流数
        json_dir = output_path / "Workflows_JSON"
        media_json_dir = output_path / "Workflows_JSON_From_Media"
        wf_count = 0
        if json_dir.exists():
            wf_count += len(list(json_dir.glob('*.json')))
        if media_json_dir.exists():
            wf_count += len(list(media_json_dir.glob('*.json')))
        self.stats_workflows.config(text=f"工作流: {wf_count}")

        # 模型数
        model_csv = output_path / "model_resources.csv"
        model_count = 0
        if model_csv.exists():
            import csv
            with open(model_csv, 'r', encoding='utf-8-sig') as f:
                model_count = sum(1 for _ in csv.reader(f)) - 1
        self.stats_models.config(text=f"模型: {model_count}")

        # 媒体数
        media_dir = output_path / "Workflows_Media"
        media_count = 0
        if media_dir.exists():
            media_count = len(list(media_dir.glob('*')))
        self.stats_media.config(text=f"媒体: {media_count}")

        # 节点数（从数据库）
        db_file = output_path / "comfyui_workflows.db"
        node_count = 0
        if db_file.exists():
            try:
                import sqlite3
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM nodes")
                node_count = cursor.fetchone()[0]
                conn.close()
            except:
                pass
        self.stats_nodes.config(text=f"节点: {node_count}")

    def clear_output_dir(self):
        """清空输出目录"""
        if not messagebox.askyesno("确认清空", "确定要清空输出目录吗？\n此操作不可恢复！"):
            return

        output_path = Path(self.output_dir)
        if output_path.exists():
            try:
                shutil.rmtree(output_path)
                self.log("输出目录已清空", 'success')
                self.refresh_stats()
            except Exception as e:
                self.log(f"清空失败: {e}", 'error')
        else:
            self.log("输出目录不存在", 'warning')

    def set_running(self, running):
        """设置运行状态"""
        self.is_running = running
        if running:
            self.btn_stop.config(state=tk.NORMAL)
            self.status_label.config(text="状态: 运行中...")
            for btn in [self.btn_scan, self.btn_models, self.btn_media, self.btn_stats,
                        self.btn_missing, self.btn_database, self.btn_export, self.btn_web, self.btn_all]:
                btn.config(state=tk.DISABLED)
        else:
            self.btn_stop.config(state=tk.DISABLED)
            self.status_label.config(text="状态: 完成")
            for btn in [self.btn_scan, self.btn_models, self.btn_media, self.btn_stats,
                        self.btn_missing, self.btn_database, self.btn_export, self.btn_web, self.btn_all]:
                btn.config(state=tk.NORMAL)

    def stop_task(self):
        """终止当前任务"""
        if self.current_process:
            self.current_process.terminate()
            self.log("任务已终止", 'warning')
        self.set_running(False)

    def run_script(self, script_name, args=None):
        """运行脚本"""
        if self.is_running:
            messagebox.showwarning("任务运行中", "请等待当前任务完成或终止")
            return

        self.set_running(True)
        self.progress_var.set(0)

        script_path = Path("F:/ComfyuiCatchJson") / script_name

        def run():
            try:
                self.log(f"开始执行: {script_name}", 'info')

                # 构建命令
                cmd = [sys.executable, str(script_path)]
                if args:
                    cmd.extend(args)

                # 设置环境变量
                env = os.environ.copy()
                env['OUTPUT_DIR'] = self.output_dir
                env['PROXY'] = self.proxy

                # 运行进程
                self.current_process = subprocess.Popen(
                    cmd,
                    cwd="F:/ComfyuiCatchJson",
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )

                # 读取输出
                progress = 10
                while True:
                    line = self.current_process.stdout.readline()
                    if not line and self.current_process.poll() is not None:
                        break
                    if line:
                        self.log(line.rstrip(), 'info')
                        # 更新进度
                        if '=' in line or '...' in line:
                            progress = min(progress + 5, 95)
                            self.progress_var.set(progress)

                if self.current_process.returncode == 0:
                    self.log(f"✓ {script_name} 完成", 'success')
                    self.progress_var.set(100)
                else:
                    self.log(f"✗ {script_name} 失败 (退出码: {self.current_process.returncode})", 'error')

            except Exception as e:
                self.log(f"执行错误: {e}", 'error')

            finally:
                self.current_process = None
                self.set_running(False)
                self.refresh_stats()

        threading.Thread(target=run, daemon=True).start()

    def run_scan(self):
        """扫描工作流"""
        if not self.scan_paths:
            messagebox.showwarning("未配置路径", "请先添加扫描路径")
            return

        # 更新comfyui_extractor.py中的路径配置
        self.update_extractor_paths()
        self.run_script("comfyui_extractor.py")

    def update_extractor_paths(self):
        """更新扫描脚本的路径配置"""
        script_path = Path("F:/ComfyuiCatchJson/comfyui_extractor.py")
        if script_path.exists():
            content = script_path.read_text(encoding='utf-8')
            # 替换SCAN_PATHS配置
            new_paths_str = "SCAN_PATHS = [\n"
            for path in self.scan_paths:
                new_paths_str += f"    r\"{path}\",\n"
            new_paths_str += "]"

            # 简单替换（假设原配置格式相同）
            import re
            content = re.sub(
                r'SCAN_PATHS = \[[^\]]+\]',
                new_paths_str,
                content,
                flags=re.MULTILINE
            )

            # 替换输出目录
            content = re.sub(
                r'OUTPUT_DIR = Path\("[^"]+"\)',
                f'OUTPUT_DIR = Path("{self.output_dir}")',
                content
            )

            script_path.write_text(content, encoding='utf-8')
            self.log("扫描路径配置已更新", 'info')

    def run_models(self):
        """提取模型资源"""
        self.run_script("extract_model_resources.py")

    def run_media(self):
        """提取媒体工作流"""
        self.run_script("extract_media_workflows.py")

    def run_stats(self):
        """生成统计分析"""
        self.run_script("workflow_stats.py")

    def run_missing(self):
        """检测缺失模型"""
        self.run_script("missing_model_detector.py")

    def run_database(self):
        """导入数据库"""
        self.run_script("database_manager.py")

    def run_export(self):
        """导出报告"""
        self.run_script("export_reports.py")

    def run_web(self):
        """启动Web界面"""
        if self.is_running:
            messagebox.showwarning("任务运行中", "请先终止当前任务")
            return

        self.log("启动Web服务器: http://localhost:8080", 'info')

        def run():
            subprocess.run([sys.executable, "F:/ComfyuiCatchJson/web_visualizer.py"])

        threading.Thread(target=run, daemon=True).start()

    def run_all(self):
        """执行全部流程"""
        if self.is_running:
            messagebox.showwarning("任务运行中", "请等待当前任务完成或终止")
            return

        if not self.scan_paths:
            messagebox.showwarning("未配置路径", "请先添加扫描路径")
            return

        self.set_running(True)
        self.log("开始执行全部流程...", 'info')

        def run():
            scripts = [
                ("comfyui_extractor.py", "扫描工作流"),
                ("extract_model_resources.py", "提取模型"),
                ("extract_media_workflows.py", "媒体工作流"),
                ("workflow_stats.py", "统计分析"),
                ("missing_model_detector.py", "缺失模型"),
                ("database_manager.py", "导入数据库"),
                ("export_reports.py", "导出报告"),
            ]

            self.update_extractor_paths()

            for i, (script, name) in enumerate(scripts):
                try:
                    self.log(f"\n[{i+1}/{len(scripts)}] {name}...", 'info')
                    self.progress_var.set((i / len(scripts)) * 100)

                    script_path = Path("F:/ComfyuiCatchJson") / script

                    env = os.environ.copy()
                    env['OUTPUT_DIR'] = self.output_dir
                    env['PROXY'] = self.proxy

                    self.current_process = subprocess.Popen(
                        [sys.executable, str(script_path)],
                        cwd="F:/ComfyuiCatchJson",
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )

                    while True:
                        line = self.current_process.stdout.readline()
                        if not line and self.current_process.poll() is not None:
                            break
                        if line:
                            self.log(line.rstrip(), 'info')

                    if self.current_process.returncode == 0:
                        self.log(f"✓ {name} 完成", 'success')
                    else:
                        self.log(f"✗ {name} 失败", 'error')

                except Exception as e:
                    self.log(f"执行错误: {e}", 'error')

            self.log("\n全部流程完成!", 'success')
            self.progress_var.set(100)
            self.current_process = None
            self.set_running(False)
            self.refresh_stats()

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()

    # 设置样式
    style = ttk.Style()
    style.theme_use('clam')

    app = ComfyUIToolGUI(root)

    # 设置图标（如果存在）
    icon_path = Path("F:/ComfyuiCatchJson/icon.ico")
    if icon_path.exists():
        root.iconbitmap(str(icon_path))

    root.mainloop()


if __name__ == "__main__":
    main()