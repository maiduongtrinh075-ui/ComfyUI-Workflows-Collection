#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 工作流 SQLite 数据库工具
将工作流、模型、映射数据存储到SQLite数据库，便于查询和分析
"""

import json
import sys
import csv
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 目录配置
BASE_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets")
JSON_DIR = BASE_DIR / "Workflows_JSON"
MEDIA_JSON_DIR = BASE_DIR / "Workflows_JSON_From_Media"
MEDIA_DIR = BASE_DIR / "Workflows_Media"
MAPPING_FILE = BASE_DIR / "media_workflow_mapping.json"
MODEL_CSV = BASE_DIR / "model_resources.csv"
OUTPUT_DB = BASE_DIR / "comfyui_workflows.db"


def init_database():
    """初始化数据库表结构"""
    conn = sqlite3.connect(OUTPUT_DB)
    cursor = conn.cursor()

    # 工作流表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS workflows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE NOT NULL,
        source TEXT NOT NULL,
        node_count INTEGER,
        link_count INTEGER,
        workflow_hash TEXT,
        json_content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 节点表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workflow_id INTEGER,
        node_type TEXT NOT NULL,
        node_index INTEGER,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    )
    ''')

    # 模型引用表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS model_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workflow_id INTEGER,
        model_type TEXT NOT NULL,
        model_name TEXT NOT NULL,
        node_type TEXT,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    )
    ''')

    # 模型资源表（从CSV）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS model_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_type TEXT NOT NULL,
        model_name TEXT NOT NULL,
        usage_count INTEGER,
        download_url TEXT,
        page_url TEXT
    )
    ''')

    # 媒体映射表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS media_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        media_file TEXT NOT NULL,
        workflow_json TEXT NOT NULL,
        workflow_hash TEXT,
        is_duplicate BOOLEAN,
        media_type TEXT,
        node_count INTEGER,
        extraction_method TEXT
    )
    ''')

    # 统计信息表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stat_type TEXT NOT NULL,
        stat_key TEXT NOT NULL,
        stat_value INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 创建索引加速查询
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_refs_type ON model_references(model_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_refs_name ON model_references(model_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflows_hash ON workflows(workflow_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_hash ON media_mappings(workflow_hash)')

    conn.commit()
    return conn


def compute_hash(data):
    """计算数据哈希"""
    content = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def extract_nodes(workflow_data):
    """从工作流提取节点"""
    nodes = []

    if 'nodes' in workflow_data:
        for idx, node in enumerate(workflow_data.get('nodes', [])):
            node_type = node.get('type', '')
            if node_type:
                nodes.append({
                    'type': node_type,
                    'index': idx,
                    'widgets_values': node.get('widgets_values', [])
                })

    else:
        for key, node in workflow_data.items():
            if isinstance(node, dict) and 'class_type' in node:
                nodes.append({
                    'type': node['class_type'],
                    'index': int(key) if key.isdigit() else 0,
                    'widgets_values': []
                })

    return nodes


def extract_models_from_node(node_type, widgets_values, inputs=None):
    """从节点提取模型引用"""
    models = []

    # Checkpoint相关
    if any(loader in node_type for loader in ['CheckpointLoader', 'UNETLoader', 'KSampler']):
        for val in widgets_values:
            if isinstance(val, str) and any(ext in val.lower() for ext in ['.safetensors', '.ckpt', '.pt', '.pth']):
                models.append({'type': 'checkpoint', 'name': val})

    # LoRA相关
    if 'LoraLoader' in node_type:
        for val in widgets_values:
            if isinstance(val, str):
                models.append({'type': 'lora', 'name': val})

    # VAE相关
    if 'VAELoader' in node_type:
        for val in widgets_values:
            if isinstance(val, str):
                models.append({'type': 'vae', 'name': val})

    # CLIP相关
    if 'CLIPLoader' in node_type:
        for val in widgets_values:
            if isinstance(val, str):
                models.append({'type': 'clip', 'name': val})

    # ControlNet相关
    if 'ControlNetLoader' in node_type:
        for val in widgets_values:
            if isinstance(val, str):
                models.append({'type': 'controlnet', 'name': val})

    # Upscale相关
    if 'UpscaleModel' in node_type:
        for val in widgets_values:
            if isinstance(val, str):
                models.append({'type': 'upscale_model', 'name': val})

    # API格式inputs检查
    if inputs:
        if 'ckpt_name' in inputs:
            models.append({'type': 'checkpoint', 'name': inputs['ckpt_name']})
        if 'lora_name' in inputs:
            models.append({'type': 'lora', 'name': inputs['lora_name']})
        if 'vae_name' in inputs:
            models.append({'type': 'vae', 'name': inputs['vae_name']})
        if 'clip_name' in inputs:
            models.append({'type': 'clip', 'name': inputs['clip_name']})
        if 'control_net_name' in inputs:
            models.append({'type': 'controlnet', 'name': inputs['control_net_name']})

    return models


def import_workflows(conn):
    """导入工作流JSON到数据库"""
    cursor = conn.cursor()

    imported = 0
    skipped = 0

    # 导入JSON目录的工作流
    for json_file in JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(json_file, encoding='utf-8'))
            wf_hash = compute_hash(data)
            nodes = extract_nodes(data)
            node_count = len(nodes)
            link_count = len(data.get('links', []))

            # 检查是否已存在
            cursor.execute('SELECT id FROM workflows WHERE filename = ?', (json_file.name,))
            if cursor.fetchone():
                skipped += 1
                continue

            # 插入工作流
            cursor.execute('''
                INSERT INTO workflows (filename, source, node_count, link_count, workflow_hash, json_content)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (json_file.name, 'json', node_count, link_count, wf_hash, json.dumps(data, ensure_ascii=False)))

            wf_id = cursor.lastrowid

            # 插入节点
            for node in nodes:
                cursor.execute('''
                    INSERT INTO nodes (workflow_id, node_type, node_index)
                    VALUES (?, ?, ?)
                ''', (wf_id, node['type'], node['index']))

                # 提取模型引用
                models = extract_models_from_node(node['type'], node['widgets_values'])
                for model in models:
                    cursor.execute('''
                        INSERT INTO model_references (workflow_id, model_type, model_name, node_type)
                        VALUES (?, ?, ?, ?)
                    ''', (wf_id, model['type'], model['name'], node['type']))

            imported += 1

        except Exception as e:
            print(f"  错误: {json_file.name}: {e}")

    # 导入媒体提取的工作流
    for json_file in MEDIA_JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(json_file, encoding='utf-8'))
            wf_hash = compute_hash(data)
            nodes = extract_nodes(data)
            node_count = len(nodes)
            link_count = len(data.get('links', []))

            cursor.execute('SELECT id FROM workflows WHERE filename = ?', (json_file.name,))
            if cursor.fetchone():
                skipped += 1
                continue

            cursor.execute('''
                INSERT INTO workflows (filename, source, node_count, link_count, workflow_hash, json_content)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (json_file.name, 'media', node_count, link_count, wf_hash, json.dumps(data, ensure_ascii=False)))

            wf_id = cursor.lastrowid

            for node in nodes:
                cursor.execute('''
                    INSERT INTO nodes (workflow_id, node_type, node_index)
                    VALUES (?, ?, ?)
                ''', (wf_id, node['type'], node['index']))

                models = extract_models_from_node(node['type'], node['widgets_values'])
                for model in models:
                    cursor.execute('''
                        INSERT INTO model_references (workflow_id, model_type, model_name, node_type)
                        VALUES (?, ?, ?, ?)
                    ''', (wf_id, model['type'], model['name'], node['type']))

            imported += 1

        except Exception as e:
            print(f"  错误: {json_file.name}: {e}")

    conn.commit()
    return imported, skipped


def import_model_resources(conn):
    """导入模型资源CSV"""
    cursor = conn.cursor()

    if not MODEL_CSV.exists():
        return 0

    imported = 0

    with open(MODEL_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute('''
                INSERT OR REPLACE INTO model_resources
                (model_type, model_name, usage_count, download_url, page_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                row.get('type', ''),
                row.get('name', ''),
                int(row.get('usage_count', 0)),
                row.get('download_url', ''),
                row.get('page_url', '')
            ))
            imported += 1

    conn.commit()
    return imported


def import_media_mappings(conn):
    """导入媒体映射"""
    cursor = conn.cursor()

    if not MAPPING_FILE.exists():
        return 0

    data = json.load(open(MAPPING_FILE, encoding='utf-8'))
    mappings = data.get('mappings', [])

    imported = 0

    for mapping in mappings:
        cursor.execute('''
            INSERT OR REPLACE INTO media_mappings
            (media_file, workflow_json, workflow_hash, is_duplicate, media_type, node_count, extraction_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            mapping.get('media_file', ''),
            mapping.get('workflow_json', ''),
            mapping.get('workflow_hash', ''),
            mapping.get('is_duplicate', False),
            mapping.get('media_type', ''),
            mapping.get('node_count', 0),
            mapping.get('extraction_method', '')
        ))
        imported += 1

    conn.commit()
    return imported


def update_statistics(conn):
    """更新统计信息"""
    cursor = conn.cursor()

    # 清空旧统计
    cursor.execute('DELETE FROM statistics')

    stats = []

    # 工作流总数
    cursor.execute('SELECT COUNT(*) FROM workflows')
    stats.append(('total', 'workflows', cursor.fetchone()[0]))

    # 节点总数
    cursor.execute('SELECT COUNT(*) FROM nodes')
    stats.append(('total', 'nodes', cursor.fetchone()[0]))

    # 模型引用总数
    cursor.execute('SELECT COUNT(*) FROM model_references')
    stats.append(('total', 'model_references', cursor.fetchone()[0]))

    # 按节点类型统计
    cursor.execute('SELECT node_type, COUNT(*) as cnt FROM nodes GROUP BY node_type ORDER BY cnt DESC LIMIT 20')
    for row in cursor.fetchall():
        stats.append(('node_type', row[0], row[1]))

    # 按模型类型统计
    cursor.execute('SELECT model_type, COUNT(*) as cnt FROM model_references GROUP BY model_type')
    for row in cursor.fetchall():
        stats.append(('model_type', row[0], row[1]))

    # 媒体映射总数
    cursor.execute('SELECT COUNT(*) FROM media_mappings')
    stats.append(('total', 'media_mappings', cursor.fetchone()[0]))

    # 唯一工作流哈希数
    cursor.execute('SELECT COUNT(DISTINCT workflow_hash) FROM media_mappings')
    stats.append(('unique', 'workflow_hashes', cursor.fetchone()[0]))

    # 插入统计
    for stat_type, stat_key, stat_value in stats:
        cursor.execute('''
            INSERT INTO statistics (stat_type, stat_key, stat_value)
            VALUES (?, ?, ?)
        ''', (stat_type, stat_key, stat_value))

    conn.commit()
    return stats


def query_examples(conn):
    """示例查询"""
    cursor = conn.cursor()

    print("\n📊 数据库查询示例:")

    # 查询热门节点
    print("\n  Top 10 热门节点:")
    cursor.execute('''
        SELECT node_type, COUNT(*) as cnt
        FROM nodes GROUP BY node_type
        ORDER BY cnt DESC LIMIT 10
    ''')
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")

    # 查询热门模型
    print("\n  Top 10 热门模型:")
    cursor.execute('''
        SELECT model_type, model_name, COUNT(*) as cnt
        FROM model_references
        GROUP BY model_name
        ORDER BY cnt DESC LIMIT 10
    ''')
    for row in cursor.fetchall():
        print(f"    [{row[0]}] {row[1]}: {row[2]}")

    # 按模型类型统计
    print("\n  模型类型分布:")
    cursor.execute('''
        SELECT model_type, COUNT(*) as cnt
        FROM model_references
        GROUP BY model_type
        ORDER BY cnt DESC
    ''')
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]}")


def main():
    print("=" * 60)
    print("ComfyUI 工作流 SQLite 数据库工具")
    print("=" * 60)

    # 初始化数据库
    print("\n[1] 初始化数据库...")
    conn = init_database()
    print(f"  数据库路径: {OUTPUT_DB}")

    # 导入工作流
    print("\n[2] 导入工作流JSON...")
    wf_imported, wf_skipped = import_workflows(conn)
    print(f"  导入: {wf_imported} 个, 跳过: {wf_skipped} 个")

    # 导入模型资源
    print("\n[3] 导入模型资源CSV...")
    model_imported = import_model_resources(conn)
    print(f"  导入: {model_imported} 条")

    # 导入媒体映射
    print("\n[4] 导入媒体映射...")
    mapping_imported = import_media_mappings(conn)
    print(f"  导入: {mapping_imported} 条")

    # 更新统计
    print("\n[5] 更新统计信息...")
    stats = update_statistics(conn)
    print(f"  统计项: {len(stats)} 条")

    # 示例查询
    query_examples(conn)

    conn.close()

    print("\n" + "=" * 60)
    print("完成!")
    print(f"数据库文件: {OUTPUT_DB}")
    print("=" * 60)

    print("\n💡 使用说明:")
    print("  - 使用 SQLite 工具或 Python sqlite3 模块查询数据库")
    print("  - 示例查询: SELECT * FROM workflows WHERE node_count > 50")
    print("  - 示例查询: SELECT * FROM nodes WHERE node_type LIKE '%Sampler%'")
    print("  - Web可视化工具可直接读取数据库")


if __name__ == "__main__":
    main()