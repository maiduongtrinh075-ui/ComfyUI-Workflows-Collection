#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型资源提取脚本：从工作流JSON中提取模型、VAE、LoRA等信息
"""

import json
import sys
import csv
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WORKFLOW_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_JSON")
OUTPUT_FILE = Path("F:/ComfyuiCatchJson/model_resources.csv")

# 模型加载节点类型映射
MODEL_NODE_TYPES = {
    'CheckpointLoaderSimple': 'checkpoint',
    'CheckpointLoader': 'checkpoint',
    'CheckpointLoaderNF4': 'checkpoint',
    'UNETLoader': 'unet',
    'VAELoader': 'vae',
    'LoraLoader': 'lora',
    'LoraLoaderModelOnly': 'lora',
    'CLIPLoader': 'clip',
    'DualCLIPLoader': 'clip',
    'TripleCLIPLoader': 'clip',
    'CLIPLoaderVideo': 'clip',
    'IPAdapterModelLoader': 'ipadapter',
    'StyleModelLoader': 'style_model',
    'UpscaleModelLoader': 'upscale_model',
    'ControlNetLoader': 'controlnet',
    'DiffControlNetLoader': 'controlnet',
    'GLIGENLoader': 'gligen',
    'HypernetworkLoader': 'hypernetwork',
}

def extract_models_from_workflow(workflow_data: dict) -> list:
    """从工作流数据中提取模型信息"""
    models = []
    nodes = workflow_data.get('nodes', [])

    for node in nodes:
        node_type = node.get('type', '')

        model_type = None
        for pattern, mtype in MODEL_NODE_TYPES.items():
            if pattern.lower() in node_type.lower():
                model_type = mtype
                break

        if model_type:
            widgets_values = node.get('widgets_values', [])

            model_name = None
            if widgets_values:
                first_val = widgets_values[0]
                if isinstance(first_val, str) and first_val.strip() and not first_val.startswith('http'):
                    model_name = first_val.strip()
                elif isinstance(first_val, list) and len(first_val) > 0:
                    if isinstance(first_val[0], str) and first_val[0].strip():
                        model_name = first_val[0].strip()

            if model_name:
                models.append({
                    'type': model_type,
                    'name': model_name,
                    'node_type': node_type,
                })

    return models

def main():
    print("=" * 60)
    print("ComfyUI 模型资源提取工具")
    print("=" * 60)

    all_models = defaultdict(lambda: {
        'type': '',
        'workflows': [],
        'count': 0,
        'node_types': set()
    })

    print("\n扫描 JSON 工作流...")
    json_files = list(WORKFLOW_DIR.glob('*.json'))
    print(f"  找到 {len(json_files)} 个工作流文件")

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            models = extract_models_from_workflow(data)
            for m in models:
                key = f"{m['type']}:{m['name']}"
                all_models[key]['type'] = m['type']
                all_models[key]['workflows'].append(json_file.name)
                all_models[key]['count'] += 1
                all_models[key]['node_types'].add(m['node_type'])
                all_models[key]['name'] = m['name']
        except Exception as e:
            pass

    print(f"\n找到 {len(all_models)} 个唯一模型")

    # 统计
    print("\n模型类型统计:")
    type_counts = defaultdict(int)
    for key, info in all_models.items():
        type_counts[info['type']] += 1

    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c} 个")

    # 导出CSV
    print(f"\n导出到: {OUTPUT_FILE}")

    results = []
    for key, info in all_models.items():
        results.append({
            'type': info['type'],
            'name': info['name'],
            'usage_count': info['count'],
            'workflows': '; '.join(info['workflows'][:3]),
            'node_types': '; '.join(info['node_types']),
            'civitai_name': '',
            'civitai_id': '',
            'download_url': '',
            'version': '',
            'page_url': ''
        })

    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['type', 'name', 'usage_count', 'node_types', 'civitai_name',
                      'civitai_id', 'version', 'download_url', 'page_url', 'workflows']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        sorted_results = sorted(results, key=lambda x: (x['type'], -x['usage_count']))
        for r in sorted_results:
            writer.writerow(r)

    print(f"  导出 {len(results)} 条记录")
    print("\n完成! 请查看: " + str(OUTPUT_FILE))

if __name__ == "__main__":
    main()