#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型下载工具
从Civitai搜索并下载缺失的模型文件
"""

import json
import sys
import os
import requests
import hashlib
import time
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 配置
OUTPUT_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets")
COMFYUI_MODELS_DIR = Path("F:/ComfyUI/models")  # 用户需要修改为实际路径
PROXY = "http://127.0.0.1:7890"

# Civitai API
CIVITAI_API_BASE = "https://civitai.com/api/v1"

# 模型类型映射
MODEL_DIR_MAP = {
    'checkpoint': 'checkpoints',
    'lora': 'loras',
    'vae': 'vae',
    'clip': 'clip',
    'controlnet': 'controlnet',
    'upscale_model': 'upscale_models',
    'unet': 'unet',
    'embedding': 'embeddings',
}


def search_civitai_model(model_name, model_type, proxy=None):
    """
    在Civitai搜索模型
    返回: (model_id, version_id, download_url, model_page_url) 或 None
    """
    try:
        # 清理模型名称
        clean_name = model_name.split('/')[-1].split('\\')[-1]
        clean_name = clean_name.replace('.safetensors', '').replace('.ckpt', '').replace('.pt', '')

        print(f"  搜索: {clean_name} ({model_type})")

        # 搜索API
        search_url = f"{CIVITAI_API_BASE}/models"
        params = {
            'query': clean_name,
            'limit': 5,
            'types': model_type if model_type in ['Checkpoint', 'LORA', 'VAE', 'TextEncoder', 'ControlNet', 'Upscaler'] else None
        }

        # 类型映射（Civitai的类别名）
        type_map = {
            'checkpoint': 'Checkpoint',
            'lora': 'LORA',
            'vae': 'VAE',
            'clip': 'TextEncoder',
            'controlnet': 'ControlNet',
            'upscale_model': 'Upscaler',
            'unet': 'Checkpoint',
        }

        if model_type in type_map:
            params['types'] = type_map[model_type]

        proxies = {'http': proxy, 'https': proxy} if proxy else None

        response = requests.get(search_url, params=params, proxies=proxies, timeout=30)
        response.raise_for_status()

        data = response.json()
        items = data.get('items', [])

        if not items:
            print(f"  ✗ 未找到模型")
            return None

        # 遍历搜索结果，找最匹配的
        for item in items:
            model_id = item.get('id')
            model_name_found = item.get('name', '')

            # 检查名称是否匹配
            if clean_name.lower() in model_name_found.lower() or model_name_found.lower() in clean_name.lower():
                # 获取版本信息
                versions = item.get('modelVersions', [])
                if versions:
                    # 选择最新版本
                    latest_version = versions[0]
                    version_id = latest_version.get('id')

                    # 获取下载文件
                    files = latest_version.get('files', [])
                    for file in files:
                        if file.get('type') == 'Model':
                            download_url = file.get('downloadUrl')
                            file_name = file.get('name', clean_name + '.safetensors')
                            file_size = file.get('sizeKB', 0) * 1024  # 转换为字节

                            model_page_url = f"https://civitai.com/models/{model_id}"

                            print(f"  ✓ 找到: {model_name_found}")
                            print(f"    版本: {latest_version.get('name', 'latest')}")
                            print(f"    文件: {file_name} ({file_size/1024/1024:.1f}MB)")
                            print(f"    页面: {model_page_url}")

                            return {
                                'model_id': model_id,
                                'version_id': version_id,
                                'download_url': download_url,
                                'file_name': file_name,
                                'file_size': file_size,
                                'model_page_url': model_page_url,
                                'model_name': model_name_found
                            }

        print(f"  ✗ 未找到精确匹配")
        return None

    except requests.exceptions.RequestException as e:
        print(f"  ✗ 搜索失败: {e}")
        return None
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return None


def download_model(download_url, target_path, proxy=None, file_size=0):
    """
    下载模型文件
    支持进度显示和断点续传
    """
    try:
        print(f"  开始下载...")
        print(f"  目标路径: {target_path}")

        proxies = {'http': proxy, 'https': proxy} if proxy else None

        # 检查是否已存在部分下载
        existing_size = 0
        if target_path.exists():
            existing_size = target_path.stat().st_size
            if existing_size == file_size and file_size > 0:
                print(f"  ✓ 文件已存在，跳过下载")
                return True

        # 开始下载
        headers = {}
        if existing_size > 0:
            headers['Range'] = f'bytes={existing_size}-'
            mode = 'ab'
        else:
            mode = 'wb'

        response = requests.get(download_url, headers=headers, proxies=proxies, stream=True, timeout=60)

        # 获取总大小
        total_size = int(response.headers.get('content-length', file_size))
        if existing_size > 0 and 'content-range' in response.headers:
            # 断点续传时，总大小从content-range获取
            content_range = response.headers['content-range']
            total_size = int(content_range.split('/')[-1])

        total_size_mb = total_size / 1024 / 1024

        downloaded = existing_size
        start_time = time.time()

        with open(target_path, mode) as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # 显示进度
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                    else:
                        progress = 0
                    downloaded_mb = downloaded / 1024 / 1024
                    total_size_mb = total_size / 1024 / 1024 if total_size > 0 else 0
                    elapsed = time.time() - start_time
                    speed = downloaded_mb / elapsed if elapsed > 0 else 0

                    # 每10%显示一次进度
                    if int(progress) % 10 == 0 and int(progress) > 0:
                        print(f"  进度: {progress:.1f}% ({downloaded_mb:.1f}/{total_size_mb:.1f}MB) - {speed:.2f}MB/s")

        print(f"  ✓ 下载完成!")
        return True

    except requests.exceptions.RequestException as e:
        print(f"  ✗ 下载失败: {e}")
        return False
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False


def test_download_one_model():
    """测试下载一个模型"""
    print("=" * 60)
    print("模型下载测试")
    print("=" * 60)

    # 选择一个常见的模型测试
    test_model = "flux1-dev.safetensors"  # Flux模型比较常见
    test_type = "checkpoint"

    print(f"\n测试模型: {test_model}")

    # 搜索模型
    result = search_civitai_model(test_model, test_type, PROXY)

    if result:
        print(f"\n找到模型信息:")
        print(f"  名称: {result['model_name']}")
        print(f"  文件: {result['file_name']}")
        print(f"  大小: {result['file_size']/1024/1024:.1f}MB")
        print(f"  下载链接: {result['download_url']}")

        # 选择下载目录
        target_dir = COMFYUI_MODELS_DIR / MODEL_DIR_MAP.get(test_type, 'checkpoints')

        if not COMFYUI_MODELS_DIR.exists():
            print(f"\n⚠️ ComfyUI模型目录不存在: {COMFYUI_MODELS_DIR}")
            print("请修改脚本中的 COMFYUI_MODELS_DIR 为实际路径")

            # 使用临时目录测试
            target_dir = Path("F:/ComfyuiCatchJson/test_download")
            target_dir.mkdir(exist_ok=True)
            print(f"使用临时目录: {target_dir}")

        target_path = target_dir / result['file_name']

        # 询问是否下载
        confirm = input(f"\n是否下载此模型? (y/n): ").strip().lower()
        if confirm == 'y':
            download_model(result['download_url'], target_path, PROXY, result['file_size'])
        else:
            print("取消下载")

    else:
        print("未找到模型，请尝试其他模型名称")


def batch_download_missing_models(max_count=5):
    """批量下载缺失模型"""
    print("=" * 60)
    print("批量下载缺失模型")
    print("=" * 60)

    # 读取缺失模型列表
    missing_csv = OUTPUT_DIR / 'missing_models.csv'
    if not missing_csv.exists():
        print("缺失模型列表不存在，请先运行 missing_model_detector.py")
        return

    import csv
    missing_models = []
    with open(missing_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            missing_models.append({
                'type': row['模型类型'],
                'name': row['模型名称'],
            })

    print(f"\n缺失模型总数: {len(missing_models)}")
    print(f"本次最多下载: {max_count}")

    downloaded = 0
    failed = 0

    for model in missing_models[:max_count * 10]:  # 尝试更多，但只下载max_count个
        if downloaded >= max_count:
            break

        print(f"\n[{downloaded+1}/{max_count}] {model['name']} ({model['type']})")

        result = search_civitai_model(model['name'], model['type'], PROXY)

        if result:
            # 创建目标目录
            target_dir = COMFYUI_MODELS_DIR / MODEL_DIR_MAP.get(model['type'], 'checkpoints')
            if not COMFYUI_MODELS_DIR.exists():
                target_dir = Path("F:/ComfyuiCatchJson/test_download") / MODEL_DIR_MAP.get(model['type'], 'checkpoints')

            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / result['file_name']

            # 下载
            if download_model(result['download_url'], target_path, PROXY, result['file_size']):
                downloaded += 1
            else:
                failed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"完成! 下载: {downloaded}, 失败: {failed}")
    print("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='模型下载工具')
    parser.add_argument('--test', action='store_true', help='测试下载一个模型')
    parser.add_argument('--batch', type=int, default=5, help='批量下载缺失模型数量')
    parser.add_argument('--model', type=str, help='指定模型名称下载')
    parser.add_argument('--type', type=str, default='checkpoint', help='模型类型')
    parser.add_argument('--proxy', type=str, default=PROXY, help='代理地址')

    args = parser.parse_args()

    # 更新代理
    proxy = args.proxy

    if args.test:
        test_download_one_model()
    elif args.model:
        print(f"下载指定模型: {args.model}")
        result = search_civitai_model(args.model, args.type, proxy)
        if result:
            target_dir = COMFYUI_MODELS_DIR / MODEL_DIR_MAP.get(args.type, 'checkpoints')
            if not COMFYUI_MODELS_DIR.exists():
                target_dir = Path("F:/ComfyuiCatchJson/test_download")
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / result['file_name']
            download_model(result['download_url'], target_path, proxy, result['file_size'])
    else:
        batch_download_missing_models(args.batch)


if __name__ == "__main__":
    main()