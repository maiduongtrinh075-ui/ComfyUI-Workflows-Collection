#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从媒体文件中提取工作流 JSON，生成一一对应的 JSON 文件
带去重功能：相同工作流只保存一份JSON，多个媒体文件指向同一JSON
"""

import json
import os
import sys
import subprocess
import hashlib
from pathlib import Path
from PIL import Image
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 路径配置
MEDIA_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_Media")
OUTPUT_JSON_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_JSON_From_Media")
MAPPING_FILE = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/media_workflow_mapping.json")

# FFprobe 路径
FFPROBE_PATH = "C:/ffmpeg/ffmpeg-8.1.1-essentials_build/bin/ffprobe.exe"

def compute_workflow_hash(workflow: dict) -> str:
    """计算工作流的SHA256哈希值，用于去重"""
    # 只计算关键字段的哈希，忽略动态字段
    key_fields = {
        'nodes': workflow.get('nodes', []),
        'links': workflow.get('links', [])
    }
    content = json.dumps(key_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

def extract_workflow_from_image(image_path: Path) -> dict:
    """从图片中提取工作流 (PNG tEXt/iTXt chunks)"""
    try:
        img = Image.open(image_path)
        workflow_keys = ['prompt', 'workflow', 'Workflow', 'Prompt', 'workflow_json', 'comfyui_workflow']

        if hasattr(img, 'text'):
            for key in workflow_keys:
                if key in img.text:
                    data = img.text[key]
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError:
                        if data.startswith('{'):
                            try:
                                return json.loads(data)
                            except:
                                pass
        img.close()
    except:
        pass
    return None

def extract_workflow_from_video(video_path: Path) -> dict:
    """从视频中提取工作流 (FFprobe 元数据)"""
    try:
        result = subprocess.run(
            [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json',
             '-show_format', str(video_path)],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            return None

        data = json.loads(result.stdout)
        tags = data.get('format', {}).get('tags', {})
        tag_keys = ['workflow', 'prompt', 'Workflow', 'Prompt', 'comment', 'description']

        for key in tag_keys:
            if key in tags:
                value = tags[key]
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    if value.startswith('{'):
                        try:
                            return json.loads(value)
                        except:
                            pass
    except:
        pass
    return None

def main():
    print("=" * 60)
    print("媒体文件工作流提取工具 (带去重)")
    print("=" * 60)

    OUTPUT_JSON_DIR.mkdir(parents=True, exist_ok=True)

    # 扫描媒体文件
    image_exts = ['.png', '.jpg', '.jpeg', '.webp', '.gif']
    video_exts = ['.mp4', '.webm', '.mov', '.mkv', '.avi']

    image_files = []
    video_files = []

    for ext in image_exts:
        image_files.extend(list(MEDIA_DIR.glob(f'*{ext}')))
    for ext in video_exts:
        video_files.extend(list(MEDIA_DIR.glob(f'*{ext}')))

    print(f"\n找到媒体文件: {len(image_files)} 图片 + {len(video_files)} 视频 = {len(image_files) + len(video_files)} 个")

    # 去重数据结构
    workflow_hashes = {}  # hash -> (json_filename, first_media_file)
    mappings = []

    total_extracted = 0
    total_duplicates = 0
    total_no_workflow = 0

    # 提取图片工作流
    print("\n[1] 提取图片工作流...")
    for i, img_file in enumerate(image_files):
        workflow = extract_workflow_from_image(img_file)

        if workflow:
            wf_hash = compute_workflow_hash(workflow)
            node_count = len(workflow.get('nodes', []))

            if wf_hash in workflow_hashes:
                # 重复工作流 - 指向已有的JSON
                existing_json = workflow_hashes[wf_hash][0]
                mappings.append({
                    'media_file': img_file.name,
                    'workflow_json': existing_json,
                    'media_type': img_file.suffix[1:],
                    'node_count': node_count,
                    'workflow_hash': wf_hash,
                    'is_duplicate': True,
                    'extraction_method': 'PNG_metadata'
                })
                total_duplicates += 1
            else:
                # 新工作流 - 保存JSON
                json_name = img_file.stem + '_workflow.json'
                json_path = OUTPUT_JSON_DIR / json_name

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)

                workflow_hashes[wf_hash] = (json_name, img_file.name)

                mappings.append({
                    'media_file': img_file.name,
                    'workflow_json': json_name,
                    'media_type': img_file.suffix[1:],
                    'node_count': node_count,
                    'workflow_hash': wf_hash,
                    'is_duplicate': False,
                    'extraction_method': 'PNG_metadata'
                })
                total_extracted += 1

            if (total_extracted + total_duplicates) % 50 == 0:
                print(f"  进度: {i+1}/{len(image_files)}")
        else:
            total_no_workflow += 1

    print(f"  图片: {total_extracted} 新工作流, {total_duplicates} 重复")

    # 提取视频工作流
    print("\n[2] 提取视频工作流...")
    video_new = 0
    video_dup = 0
    video_no = 0

    for video_file in video_files:
        workflow = extract_workflow_from_video(video_file)

        if workflow:
            wf_hash = compute_workflow_hash(workflow)
            node_count = len(workflow.get('nodes', []))

            if wf_hash in workflow_hashes:
                existing_json = workflow_hashes[wf_hash][0]
                mappings.append({
                    'media_file': video_file.name,
                    'workflow_json': existing_json,
                    'media_type': video_file.suffix[1:],
                    'node_count': node_count,
                    'workflow_hash': wf_hash,
                    'is_duplicate': True,
                    'extraction_method': 'FFprobe_metadata'
                })
                video_dup += 1
                print(f"  ⊙ {video_file.name} (重复)")
            else:
                json_name = video_file.stem + '_workflow.json'
                json_path = OUTPUT_JSON_DIR / json_name

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, ensure_ascii=False, indent=2)

                workflow_hashes[wf_hash] = (json_name, video_file.name)

                mappings.append({
                    'media_file': video_file.name,
                    'workflow_json': json_name,
                    'media_type': video_file.suffix[1:],
                    'node_count': node_count,
                    'workflow_hash': wf_hash,
                    'is_duplicate': False,
                    'extraction_method': 'FFprobe_metadata'
                })
                video_new += 1
                print(f"  ✓ {video_file.name}")
        else:
            video_no += 1
            print(f"  ✗ {video_file.name}")

    total_extracted += video_new
    total_duplicates += video_dup
    total_no_workflow += video_no

    print(f"  视频: {video_new} 新工作流, {video_dup} 重复, {video_no} 无工作流")

    # 保存映射表
    print("\n[3] 保存映射表...")

    unique_workflows = len(workflow_hashes)

    mapping_data = {
        'description': '媒体文件与工作流 JSON 的对应关系 (已去重)',
        'total_media_files': len(image_files) + len(video_files),
        'unique_workflows': unique_workflows,
        'duplicate_workflows': total_duplicates,
        'no_workflow_files': total_no_workflow,
        'mappings': mappings
    }

    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

    print(f"  保存: {MAPPING_FILE}")

    # 最终统计
    print("\n" + "=" * 60)
    print("完成!")
    print(f"  唯一工作流: {unique_workflows} 个")
    print(f"  重复工作流: {total_duplicates} 个")
    print(f"  无工作流: {total_no_workflow} 个")
    print(f"  JSON文件数: {unique_workflows} 个 (去重)")
    print(f"  输出目录: {OUTPUT_JSON_DIR}")
    print("=" * 60)

    print("\n使用说明:")
    print("  - 每个媒体文件都有对应记录，指向工作流JSON")
    print("  - 重复工作流共享同一个JSON文件")
    print("  - workflow_hash 字段用于识别相同工作流")

if __name__ == "__main__":
    main()