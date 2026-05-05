#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去重脚本：清理 Extracted_ComfyUI_Assets 目录中的重复文件
基于 SHA256 哈希值去重，保留最早提取的文件
"""

import hashlib
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 解决 Windows 控制台编码问题
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets")
HISTORY_FILE = OUTPUT_DIR / "scanned_history.json"


def calculate_file_hash(file_path: Path) -> str:
    """计算文件 SHA256 哈希"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def find_duplicates(directory: Path) -> dict:
    """
    扫描目录，找出所有重复文件
    返回: {哈希值: [文件路径列表]}
    """
    hash_map = defaultdict(list)

    print(f"扫描目录: {directory}")
    for file_path in directory.rglob('*'):
        if not file_path.is_file():
            continue

        try:
            file_hash = calculate_file_hash(file_path)
            hash_map[file_hash].append(file_path)
        except Exception as e:
            print(f"  跳过: {file_path.name} - {e}")

    return hash_map


def deduplicate(hash_map: dict, keep_strategy: str = "oldest") -> tuple:
    """
    根据哈希值去重
    keep_strategy: 'oldest' 保留最早创建的文件, 'shortest_name' 保留文件名最短的
    返回: (保留文件列表, 删除文件列表)
    """
    keep_files = []
    delete_files = []

    for file_hash, files in hash_map.items():
        if len(files) == 1:
            continue  # 无重复

        # 按策略排序，决定保留哪个
        if keep_strategy == "oldest":
            # 按创建时间排序（最早的保留）
            files_sorted = sorted(files, key=lambda f: f.stat().st_ctime)
        elif keep_strategy == "shortest_name":
            # 按文件名长度排序（最短的保留）
            files_sorted = sorted(files, key=lambda f: len(f.name))
        else:
            files_sorted = files

        keep_files.append(files_sorted[0])
        delete_files.extend(files_sorted[1:])

    return keep_files, delete_files


def generate_new_names(files: list) -> dict:
    """
    为保留的文件生成简化文件名（去掉时间戳和UUID后缀）
    返回: {原路径: 新文件名}
    """
    rename_map = {}

    for file_path in files:
        name = file_path.name
        # 模式: 原名_时间戳_UUID_计数.后缀 或 原名_UUID_计数.后缀
        # 尝试去掉 _xxxx_xxxx_x 数字后缀
        stem = file_path.stem
        suffix = file_path.suffix

        # 去掉末尾的 _数字_数字_数字 模式
        # 匹配 _hash8chars_counter 或 _hash8chars 格式
        cleaned_stem = re.sub(r'_[a-f0-9]{8}(_\d+)?$', '', stem)
        # 再次匹配 _datetime_counter 格式
        cleaned_stem = re.sub(r'_\d{8}_\d{6}(_\d+)?$', '', cleaned_stem)

        new_name = f"{cleaned_stem}{suffix}"
        if new_name != name:
            rename_map[file_path] = new_name

    return rename_map


def main():
    print("=" * 60)
    print("ComfyUI 工作流去重工具")
    print("=" * 60)

    # 扫描所有子目录
    subdirs = ["Workflows_JSON", "Workflows_Media", "Workflows_Unknown", "Archives"]

    total_files = 0
    total_duplicates = 0
    all_hash_map = defaultdict(list)

    for subdir in subdirs:
        dir_path = OUTPUT_DIR / subdir
        if not dir_path.exists():
            continue

        print(f"\n扫描 {subdir}...")
        hash_map = find_duplicates(dir_path)

        for file_hash, files in hash_map.items():
            all_hash_map[file_hash].extend(files)
            if len(files) > 1:
                dup_count = len(files) - 1
                total_duplicates += dup_count
                print(f"  发现重复: {files[0].name} ({dup_count} 个副本)")

        file_count = sum(1 for f in dir_path.rglob('*') if f.is_file())
        total_files += file_count
        print(f"  共 {file_count} 个文件")

    print("\n" + "=" * 60)
    print(f"总扫描文件: {total_files}")
    print(f"发现重复文件: {total_duplicates}")
    print("=" * 60)

    if total_duplicates == 0:
        print("没有重复文件，无需处理")
        return

    # 执行去重
    keep_files, delete_files = deduplicate(all_hash_map, keep_strategy="oldest")

    print(f"\n将删除 {len(delete_files)} 个重复文件")
    print(f"将保留 {len(keep_files)} 个唯一文件")

    # 自动确认（无需交互）
    print("\n自动确认删除重复文件...")

    # 删除重复文件
    deleted_count = 0
    failed_files = []
    for file_path in delete_files:
        try:
            file_path.unlink()
            deleted_count += 1
            print(f"  删除: {file_path.name}")
        except Exception as e:
            failed_files.append((file_path, str(e)))
            print(f"  删除失败: {file_path.name} - {e}")

    print(f"\n已删除 {deleted_count} 个重复文件")
    if failed_files:
        print(f"删除失败 {len(failed_files)} 个文件（可能需要手动删除）")

    # 生成简化文件名映射
    rename_map = generate_new_names(keep_files)
    if rename_map:
        print(f"\n发现 {len(rename_map)} 个可简化的文件名")
        print("自动简化文件名...")

        renamed_count = 0
        for old_path, new_name in rename_map.items():
            try:
                new_path = old_path.parent / new_name
                # 如果目标文件已存在，跳过
                if new_path.exists() and new_path != old_path:
                    print(f"  跳过（目标已存在）: {new_name}")
                    continue
                old_path.rename(new_path)
                renamed_count += 1
                print(f"  重命名: {old_path.name} -> {new_name}")
            except Exception as e:
                print(f"  重命名失败: {old_path.name} - {e}")

        print(f"\n已重命名 {renamed_count} 个文件")

    # 更新历史记录文件
    print("\n更新历史记录...")
    history_hashes = set(all_hash_map.keys())
    history_files = []
    for subdir in subdirs:
        dir_path = OUTPUT_DIR / subdir
        if dir_path.exists():
            for f in dir_path.rglob('*'):
                if f.is_file():
                    history_files.append(str(f.resolve()))

    history = {
        'last_scan': datetime.now().isoformat(),
        'files': history_files,
        'hashes': list(history_hashes),
        'dedup': True
    }

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"历史记录已保存: {HISTORY_FILE}")
    print(f"包含 {len(history_files)} 个文件路径, {len(history_hashes)} 个哈希值")

    print("\n" + "=" * 60)
    print("去重完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()