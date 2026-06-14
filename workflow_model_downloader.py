#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流模型下载器
针对单个工作流，检测并下载其所需的全部缺失模型
"""

import json
import sys
import os
import requests
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 配置（统一从 paths 模块取）
from paths import (  # noqa: E402
    COMFYUI_MODELS_DIR,
    PROXY,
    MODEL_DIR_MAP,
    WORKFLOWS_JSON_DIR,
    WORKFLOWS_JSON_FROM_MEDIA_DIR,
)


def parse_workflow_models(workflow_path):
    """从工作流JSON解析所有引用的模型"""
    models = defaultdict(list)

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"读取工作流失败: {e}")
        return models

    # 标准 nodes/links 格式
    if 'nodes' in data:
        for node in data.get('nodes', []):
            node_type = node.get('type', '')
            widgets_values = node.get('widgets_values', [])

            # Checkpoint相关节点
            if any(loader in node_type for loader in ['CheckpointLoader', 'UNETLoader', 'KSampler']):
                for val in widgets_values:
                    if isinstance(val, str) and any(ext in val.lower() for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']):
                        # 清理路径，只取文件名
                        clean_name = val.split('/')[-1].split('\\')[-1]
                        models['checkpoint'].append(clean_name)

            # LoRA相关节点
            elif 'LoraLoader' in node_type:
                for val in widgets_values:
                    if isinstance(val, str) and val:
                        clean_name = val.split('/')[-1].split('\\')[-1]
                        models['lora'].append(clean_name)

            # VAE相关节点
            elif 'VAELoader' in node_type:
                for val in widgets_values:
                    if isinstance(val, str) and val:
                        clean_name = val.split('/')[-1].split('\\')[-1]
                        models['vae'].append(clean_name)

            # CLIP相关节点
            elif 'CLIPLoader' in node_type:
                for val in widgets_values:
                    if isinstance(val, str) and val:
                        clean_name = val.split('/')[-1].split('\\')[-1]
                        models['clip'].append(clean_name)

            # ControlNet相关节点
            elif 'ControlNetLoader' in node_type:
                for val in widgets_values:
                    if isinstance(val, str) and val:
                        clean_name = val.split('/')[-1].split('\\')[-1]
                        models['controlnet'].append(clean_name)

            # Upscale相关节点
            elif 'UpscaleModel' in node_type:
                for val in widgets_values:
                    if isinstance(val, str) and val:
                        clean_name = val.split('/')[-1].split('\\')[-1]
                        models['upscale_model'].append(clean_name)

    # API格式（节点ID作为键）
    else:
        for key, node in data.items():
            if isinstance(node, dict):
                class_type = node.get('class_type', '')
                inputs = node.get('inputs', {})

                if any(loader in class_type for loader in ['CheckpointLoader', 'UNETLoader']):
                    model_name = inputs.get('ckpt_name', inputs.get('unet_name', inputs.get('checkpoint_name', '')))
                    if model_name:
                        clean_name = model_name.split('/')[-1].split('\\')[-1]
                        models['checkpoint'].append(clean_name)

                elif 'LoraLoader' in class_type:
                    lora_name = inputs.get('lora_name', inputs.get('model_name', ''))
                    if lora_name:
                        clean_name = lora_name.split('/')[-1].split('\\')[-1]
                        models['lora'].append(clean_name)

                elif 'VAELoader' in class_type:
                    vae_name = inputs.get('vae_name', '')
                    if vae_name:
                        clean_name = vae_name.split('/')[-1].split('\\')[-1]
                        models['vae'].append(clean_name)

                elif 'CLIPLoader' in class_type:
                    clip_name = inputs.get('clip_name', '')
                    if clip_name:
                        clean_name = clip_name.split('/')[-1].split('\\')[-1]
                        models['clip'].append(clean_name)

                elif 'ControlNetLoader' in class_type:
                    cn_name = inputs.get('control_net_name', inputs.get('controlnet_name', ''))
                    if cn_name:
                        clean_name = cn_name.split('/')[-1].split('\\')[-1]
                        models['controlnet'].append(clean_name)

                elif 'UpscaleModelLoader' in class_type:
                    upscale_name = inputs.get('model_name', '')
                    if upscale_name:
                        clean_name = upscale_name.split('/')[-1].split('\\')[-1]
                        models['upscale_model'].append(clean_name)

    # 去重
    for model_type in models:
        models[model_type] = list(set(models[model_type]))

    return models


def scan_local_models(models_dir):
    """扫描本地ComfyUI模型目录"""
    local_models = defaultdict(set)

    if not models_dir.exists():
        print(f"警告: 模型目录不存在: {models_dir}")
        return local_models

    for model_type, subdir in MODEL_DIR_MAP.items():
        model_dir = models_dir / subdir
        if model_dir.exists():
            # 扫描模型文件
            for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']:
                for model_file in model_dir.glob(f'*{ext}'):
                    local_models[model_type].add(model_file.name)

            # 也检查子目录
            for subfolder in model_dir.iterdir():
                if subfolder.is_dir():
                    for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']:
                        for model_file in subfolder.glob(f'**/*{ext}'):
                            rel_path = model_file.relative_to(model_dir)
                            local_models[model_type].add(str(rel_path))

    return local_models


def check_missing_models(workflow_models, local_models):
    """检查缺失的模型"""
    missing = defaultdict(list)
    found = defaultdict(list)

    for model_type, model_list in workflow_models.items():
        for model_name in model_list:
            # 检查是否存在
            clean_name = model_name.split('/')[-1].split('\\')[-1]

            if clean_name in local_models.get(model_type, set()):
                found[model_type].append(model_name)
            elif any(clean_name == m.split('/')[-1].split('\\')[-1] for m in local_models.get(model_type, set())):
                found[model_type].append(model_name)
            else:
                missing[model_type].append(model_name)

    return missing, found


def search_and_download_model(model_name, model_type, target_dir, proxy):
    """搜索并下载模型"""
    from model_downloader import search_civitai_model, download_model

    print(f"\n  搜索: {model_name} ({model_type})")

    result = search_civitai_model(model_name, model_type, proxy)

    if result:
        print(f"  ✓ 找到: {result['model_name']} ({result['file_size']/1024/1024:.1f}MB)")

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / result['file_name']

        print(f"  下载到: {target_path}")

        if download_model(result['download_url'], target_path, proxy, result['file_size']):
            print(f"  ✓ 下载完成!")
            return True
        else:
            print(f"  ✗ 下载失败")
            return False
    else:
        print(f"  ✗ 未找到模型")
        return False


def download_workflow_models(workflow_path, models_dir=None, proxy=None):
    """下载工作流所需的全部缺失模型"""
    print("=" * 60)
    print("工作流模型下载器")
    print("=" * 60)

    workflow_path = Path(workflow_path)
    if not workflow_path.exists():
        print(f"错误: 工作流文件不存在: {workflow_path}")
        return

    if models_dir is None:
        models_dir = COMFYUI_MODELS_DIR
    if proxy is None:
        proxy = PROXY

    print(f"\n工作流: {workflow_path.name}")
    print(f"模型目录: {models_dir}")
    print(f"代理: {proxy}")

    # 1. 解析工作流模型
    print("\n[1] 解析工作流引用的模型...")
    workflow_models = parse_workflow_models(workflow_path)

    total_workflow = sum(len(v) for v in workflow_models.values())
    print(f"  工作流引用模型: {total_workflow} 个")

    for model_type, model_list in workflow_models.items():
        if model_list:
            print(f"  {model_type}: {len(model_list)} 个")
            for model in model_list[:5]:
                print(f"    - {model}")
            if len(model_list) > 5:
                print(f"    ... 还有 {len(model_list)-5} 个")

    if total_workflow == 0:
        print("  未找到任何模型引用")
        return

    # 2. 扫描本地模型
    print("\n[2] 扫描本地模型目录...")
    local_models = scan_local_models(models_dir)

    total_local = sum(len(v) for v in local_models.values())
    print(f"  本地已有模型: {total_local} 个")

    for model_type, model_set in local_models.items():
        if model_set:
            print(f"  {model_type}: {len(model_set)} 个")

    # 3. 检查缺失模型
    print("\n[3] 检查缺失模型...")
    missing, found = check_missing_models(workflow_models, local_models)

    total_missing = sum(len(v) for v in missing.values())
    total_found = sum(len(v) for v in found.values())

    print(f"  缺失模型: {total_missing} 个")
    print(f"  已有模型: {total_found} 个")

    if total_missing == 0:
        print("\n✓ 所有模型都已存在，无需下载!")
        return

    # 显示缺失模型详情
    print("\n缺失模型列表:")
    for model_type, model_list in missing.items():
        if model_list:
            print(f"\n  {model_type}:")
            for model in model_list:
                print(f"    ✗ {model}")

    # 4. 下载缺失模型
    print("\n[4] 开始下载缺失模型...")

    downloaded = 0
    failed = 0

    for model_type, model_list in missing.items():
        if model_list:
            print(f"\n下载 {model_type} 类型模型:")
            target_dir = models_dir / MODEL_DIR_MAP.get(model_type, model_type)

            for model_name in model_list:
                if search_and_download_model(model_name, model_type, target_dir, proxy):
                    downloaded += 1
                else:
                    failed += 1

    # 5. 总结
    print("\n" + "=" * 60)
    print("下载完成!")
    print("=" * 60)
    print(f"  成功下载: {downloaded} 个")
    print(f"  下载失败: {failed} 个")
    print(f"  已有模型: {total_found} 个")
    print(f"  模型目录: {models_dir}")

    if failed > 0:
        print("\n未找到的模型可能需要手动下载:")
        for model_type, model_list in missing.items():
            for model in model_list:
                print(f"  - {model} ({model_type})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='工作流模型下载器')
    parser.add_argument('workflow', type=str, nargs='?', help='工作流JSON文件路径')
    parser.add_argument('--models-dir', type=str, default=str(COMFYUI_MODELS_DIR), help='ComfyUI模型目录')
    parser.add_argument('--proxy', type=str, default=PROXY, help='代理地址')
    parser.add_argument('--list', action='store_true', help='只列出模型，不下载')

    args = parser.parse_args()

    if args.workflow:
        workflow_path = Path(args.workflow)
        models_dir = Path(args.models_dir)

        if args.list:
            # 只列出模型
            workflow_models = parse_workflow_models(workflow_path)
            print(f"\n工作流 {workflow_path.name} 引用的模型:")
            for model_type, model_list in workflow_models.items():
                if model_list:
                    print(f"\n{model_type}:")
                    for model in model_list:
                        print(f"  - {model}")
        else:
            download_workflow_models(workflow_path, models_dir, args.proxy)
    else:
        # 交互式选择工作流
        print("=" * 60)
        print("请选择工作流文件")
        print("=" * 60)

        # 列出可用的工作流
        json_dirs = [
            WORKFLOWS_JSON_DIR,
            WORKFLOWS_JSON_FROM_MEDIA_DIR,
        ]

        workflows = []
        for json_dir in json_dirs:
            if json_dir.exists():
                workflows.extend(list(json_dir.glob('*.json')))

        if not workflows:
            print("未找到任何工作流文件")
            return

        print(f"\n找到 {len(workflows)} 个工作流:")
        for i, wf in enumerate(workflows[:20], 1):
            print(f"  {i}. {wf.name}")

        if len(workflows) > 20:
            print(f"  ... 还有 {len(workflows)-20} 个")

        # 选择
        try:
            choice = input("\n输入序号选择工作流 (或输入文件路径): ").strip()

            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(workflows):
                    workflow_path = workflows[idx]
                else:
                    print("序号超出范围")
                    return
            else:
                workflow_path = Path(choice)

            download_workflow_models(workflow_path, Path(args.models_dir), args.proxy)

        except KeyboardInterrupt:
            print("\n已取消")


if __name__ == "__main__":
    main()