#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缺失模型检测工具
对比工作流引用的模型与本地ComfyUI模型目录，找出缺失的模型
"""

import json
import sys
import csv
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 目录配置
JSON_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_JSON")
MEDIA_JSON_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_JSON_From_Media")
MODEL_RESOURCES_CSV = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/model_resources.csv")
OUTPUT_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets")

# ComfyUI本地模型目录（用户需要修改为实际路径）
LOCAL_MODEL_BASE = Path("F:/ComfyUI/models")

# 模型类型对应的子目录映射
MODEL_DIR_MAP = {
    'checkpoint': 'checkpoints',
    'lora': 'loras',
    'vae': 'vae',
    'clip': 'clip',
    'controlnet': 'controlnet',
    'upscale_model': 'upscale_models',
    'unet': 'unet',
    'embedding': 'embeddings',
    'style_model': 'style_models',
}


def load_workflow_models():
    """从工作流JSON中提取所有引用的模型"""
    models = defaultdict(set)  # type -> set of model names

    # 加载JSON目录的工作流
    for json_file in JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(json_file, encoding='utf-8'))
            extract_models_from_workflow(data, models, json_file.name)
        except:
            pass

    # 加载媒体提取的工作流
    for json_file in MEDIA_JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(json_file, encoding='utf-8'))
            extract_models_from_workflow(data, models, json_file.name)
        except:
            pass

    return models


def extract_models_from_workflow(workflow_data, models, source_file):
    """从单个工作流提取模型名称"""
    # 标准 nodes/links 格式
    if 'nodes' in workflow_data:
        for node in workflow_data.get('nodes', []):
            node_type = node.get('type', '')
            widgets_values = node.get('widgets_values', [])

            # KSampler节点检查checkpoint
            if 'KSampler' in node_type or 'Sampler' in node_type:
                for val in widgets_values:
                    if isinstance(val, str) and any(ext in val.lower() for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']):
                        models['checkpoint'].add(val)

            # Load节点检查各种模型
            elif any(loader in node_type for loader in ['LoadCheckpoint', 'CheckpointLoader', 'UNETLoader']):
                for val in widgets_values:
                    if isinstance(val, str):
                        models['checkpoint'].add(val)

            elif any(loader in node_type for loader in ['LoraLoader', 'LoRALoader']):
                for val in widgets_values:
                    if isinstance(val, str):
                        models['lora'].add(val)

            elif any(loader in node_type for loader in ['VAELoader', 'LoadVAE']):
                for val in widgets_values:
                    if isinstance(val, str):
                        models['vae'].add(val)

            elif any(loader in node_type for loader in ['CLIPLoader', 'CLIPLoader']):
                for val in widgets_values:
                    if isinstance(val, str):
                        models['clip'].add(val)

            elif any(loader in node_type for loader in ['ControlNetLoader', 'ControlNetApply']):
                for val in widgets_values:
                    if isinstance(val, str):
                        models['controlnet'].add(val)

            elif any(loader in node_type for loader in ['UpscaleModelLoader', 'UpscaleModel']):
                for val in widgets_values:
                    if isinstance(val, str):
                        models['upscale_model'].add(val)

    # API格式 (class_type)
    else:
        for key, node in workflow_data.items():
            if isinstance(node, dict):
                class_type = node.get('class_type', '')
                inputs = node.get('inputs', {})

                if any(loader in class_type for loader in ['CheckpointLoader', 'UNETLoader']):
                    model_name = inputs.get('ckpt_name', inputs.get('unet_name', ''))
                    if model_name:
                        models['checkpoint'].add(model_name)

                elif 'LoraLoader' in class_type:
                    lora_name = inputs.get('lora_name', '')
                    if lora_name:
                        models['lora'].add(lora_name)

                elif 'VAELoader' in class_type:
                    vae_name = inputs.get('vae_name', '')
                    if vae_name:
                        models['vae'].add(vae_name)

                elif 'CLIPLoader' in class_type:
                    clip_name = inputs.get('clip_name', '')
                    if clip_name:
                        models['clip'].add(clip_name)

                elif 'ControlNetLoader' in class_type:
                    cn_name = inputs.get('control_net_name', '')
                    if cn_name:
                        models['controlnet'].add(cn_name)

                elif 'UpscaleModelLoader' in class_type:
                    upscale_name = inputs.get('model_name', '')
                    if upscale_name:
                        models['upscale_model'].add(upscale_name)


def scan_local_models():
    """扫描本地ComfyUI模型目录"""
    local_models = defaultdict(set)

    if not LOCAL_MODEL_BASE.exists():
        print(f"警告: 本地模型目录不存在: {LOCAL_MODEL_BASE}")
        print("请修改脚本中的 LOCAL_MODEL_BASE 为实际路径")
        return local_models

    for model_type, subdir in MODEL_DIR_MAP.items():
        model_dir = LOCAL_MODEL_BASE / subdir
        if model_dir.exists():
            # 扫描模型文件
            for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']:
                for model_file in model_dir.glob(f'*{ext}'):
                    local_models[model_type].add(model_file.name)

            # 也检查子目录（某些模型可能按作者分类）
            for subfolder in model_dir.iterdir():
                if subfolder.is_dir():
                    for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']:
                        for model_file in subfolder.glob(f'**/*{ext}'):
                            # 存储相对路径
                            rel_path = model_file.relative_to(model_dir)
                            local_models[model_type].add(str(rel_path))

    return local_models


def compare_models(workflow_models, local_models):
    """对比工作流模型与本地模型，找出缺失的"""
    missing = defaultdict(list)
    found = defaultdict(list)

    for model_type, workflow_set in workflow_models.items():
        for model_name in workflow_set:
            # 清理模型名称（去除路径前缀）
            clean_name = model_name.split('/')[-1] if '/' in model_name else model_name

            # 检查是否存在
            if clean_name in local_models.get(model_type, set()):
                found[model_type].append(model_name)
            elif any(clean_name == m.split('/')[-1] for m in local_models.get(model_type, set())):
                found[model_type].append(model_name)
            else:
                missing[model_type].append(model_name)

    return missing, found


def generate_missing_report(missing, found, workflow_models, output_path):
    """生成缺失模型HTML报告"""
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ComfyUI 缺失模型检测报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #d32f2f; border-bottom: 2px solid #d32f2f; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .stat-box { background: #fff3e0; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #ff9800; }
        .found-box { background: #e8f5e9; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #4CAF50; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #d32f2f; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
        .missing { color: #d32f2f; font-weight: bold; }
        .found { color: #4CAF50; }
        .section { margin: 20px 0; padding: 15px; background: #fafafa; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚠️ ComfyUI 缺失模型检测报告</h1>
"""

    # 总体统计
    total_workflow = sum(len(v) for v in workflow_models.values())
    total_missing = sum(len(v) for v in missing.values())
    total_found = sum(len(v) for v in found.values())

    html += f"""
        <div class="stat-box">
            <h2>📊 总体统计</h2>
            <p><strong>工作流引用模型总数:</strong> {total_workflow} 个</p>
            <p><strong class="missing">缺失模型:</strong> {total_missing} 个 ({total_missing/total_workflow*100:.1f}%)</p>
            <p><strong class="found">已有模型:</strong> {total_found} 个 ({total_found/total_workflow*100:.1f}%)</p>
        </div>
"""

    # 缺失模型详情
    html += """
        <h2>❌ 缺失模型列表</h2>
"""

    for model_type, model_list in sorted(missing.items()):
        if model_list:
            html += f"""
        <div class="section">
            <h3>{model_type} ({len(model_list)} 个缺失)</h3>
            <table>
                <tr><th>序号</th><th>模型名称</th><th>建议目录</th></tr>
"""
            for i, model_name in enumerate(sorted(set(model_list)), 1):
                suggest_dir = MODEL_DIR_MAP.get(model_type, model_type)
                html += f"<tr><td>{i}</td><td class='missing'>{model_name}</td><td>models/{suggest_dir}/</td></tr>\n"

            html += """
            </table>
        </div>
"""

    # 已有模型详情
    html += """
        <h2>✅ 已有模型列表</h2>
"""

    for model_type, model_list in sorted(found.items()):
        if model_list:
            html += f"""
        <div class="found-box">
            <h3>{model_type} ({len(model_list)} 个已有)</h3>
            <ul>
"""
            for model_name in sorted(set(model_list))[:20]:  # 只显示前20个避免过长
                html += f"<li class='found'>{model_name}</li>\n"
            if len(model_list) > 20:
                html += f"<li>... 还有 {len(model_list)-20} 个</li>\n"

            html += """
            </ul>
        </div>
"""

    html += """
        <h2>💡 操作建议</h2>
        <div class="section">
            <p>1. 下载缺失的模型文件到对应的 ComfyUI models 子目录</p>
            <p>2. 使用 extract_model_resources.py 中的 Civitai 链接下载模型</p>
            <p>3. 查看缺失模型CSV报告: missing_models.csv</p>
        </div>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def export_missing_csv(missing, output_dir):
    """导出缺失模型CSV"""
    csv_path = output_dir / 'missing_models.csv'

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['模型类型', '模型名称', '建议目录', '缺失数量'])

        for model_type, model_list in sorted(missing.items()):
            if model_list:
                suggest_dir = MODEL_DIR_MAP.get(model_type, model_type)
                for model_name in sorted(set(model_list)):
                    writer.writerow([model_type, model_name, f'models/{suggest_dir}/', len(model_list)])

    return csv_path


def main():
    print("=" * 60)
    print("缺失模型检测工具")
    print("=" * 60)

    # 加载工作流模型
    print("\n[1] 提取工作流引用的模型...")
    workflow_models = load_workflow_models()

    total_wf = sum(len(v) for v in workflow_models.values())
    print(f"  工作流引用模型: {total_wf} 个")

    for model_type, model_set in sorted(workflow_models.items()):
        if model_set:
            print(f"  {model_type}: {len(model_set)} 个")

    # 扫描本地模型
    print("\n[2] 扫描本地ComfyUI模型目录...")
    print(f"  扫描路径: {LOCAL_MODEL_BASE}")

    local_models = scan_local_models()

    total_local = sum(len(v) for v in local_models.values())
    print(f"  本地已有模型: {total_local} 个")

    for model_type, model_set in sorted(local_models.items()):
        if model_set:
            print(f"  {model_type}: {len(model_set)} 个")

    # 对比模型
    print("\n[3] 对比工作流模型与本地模型...")
    missing, found = compare_models(workflow_models, local_models)

    total_missing = sum(len(v) for v in missing.values())
    total_found = sum(len(v) for v in found.values())

    print(f"  缺失模型: {total_missing} 个 ({total_missing/total_wf*100:.1f}%)")
    print(f"  已有模型: {total_found} 个 ({total_found/total_wf*100:.1f}%)")

    # 生成报告
    print("\n[4] 生成报告...")
    html_path = OUTPUT_DIR / 'missing_models_report.html'
    generate_missing_report(missing, found, workflow_models, html_path)
    print(f"  HTML报告: {html_path}")

    # 导出CSV
    csv_path = export_missing_csv(missing, OUTPUT_DIR)
    print(f"  CSV报告: {csv_path}")

    # 输出统计
    print("\n" + "=" * 60)
    print("检测完成!")
    print("=" * 60)

    if total_missing > 0:
        print("\n⚠️ 缺失模型最多的类型:")
        for model_type, model_list in sorted(missing.items(), key=lambda x: -len(x[1]))[:5]:
            print(f"  {model_type}: {len(model_list)} 个")
            for model_name in sorted(set(model_list))[:3]:
                print(f"    - {model_name}")
            if len(model_list) > 3:
                print(f"    ... 还有 {len(model_list)-3} 个")

    print(f"\n请打开: {html_path}")


if __name__ == "__main__":
    main()