#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 工作流报告导出工具
导出综合HTML报告和Excel格式报告
"""

import json
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 目录配置（统一从 paths 模块取）
from paths import OUTPUT_DIR as BASE_DIR, DB_FILE as DB_PATH  # noqa: E402
OUTPUT_DIR = BASE_DIR


def generate_comprehensive_html_report():
    """生成综合HTML报告"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 获取统计数据
    stats = {}
    cursor.execute('SELECT stat_type, stat_key, stat_value FROM statistics')
    for row in cursor.fetchall():
        key = f"{row[0]}_{row[1]}"
        stats[key] = row[2]

    # 获取热门节点
    cursor.execute('''
        SELECT node_type, COUNT(*) as cnt
        FROM nodes GROUP BY node_type
        ORDER BY cnt DESC LIMIT 50
    ''')
    top_nodes = cursor.fetchall()

    # 获取热门模型
    cursor.execute('''
        SELECT model_type, model_name, COUNT(*) as cnt
        FROM model_references
        GROUP BY model_name
        ORDER BY cnt DESC LIMIT 50
    ''')
    top_models = cursor.fetchall()

    # 获取模型类型分布
    cursor.execute('''
        SELECT model_type, COUNT(*) as cnt
        FROM model_references
        GROUP BY model_type
        ORDER BY cnt DESC
    ''')
    model_types = cursor.fetchall()

    # 获取复杂度分布
    cursor.execute('''
        SELECT
            CASE
                WHEN node_count < 20 THEN '简单(<20)'
                WHEN node_count < 50 THEN '中等(20-50)'
                WHEN node_count < 100 THEN '复杂(50-100)'
                ELSE '超复杂(>100)'
            END as category,
            COUNT(*) as cnt
        FROM workflows
        GROUP BY category
    ''')
    complexity = cursor.fetchall()

    # 获取最新工作流
    cursor.execute('''
        SELECT filename, source, node_count, link_count, created_at
        FROM workflows
        ORDER BY created_at DESC LIMIT 20
    ''')
    recent_workflows = cursor.fetchall()

    conn.close()

    # 生成HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ComfyUI 工作流综合分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f7fa; color: #333; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .section {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
        .section h2 {{ color: #667eea; margin-bottom: 15px; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .stat-box {{ background: #f8f9fa; border-radius: 8px; padding: 15px; text-align: center; }}
        .stat-number {{ font-size: 32px; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #e1e4e8; padding: 10px; text-align: left; }}
        th {{ background: #667eea; color: white; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .chart-container {{ display: flex; gap: 20px; margin-top: 15px; }}
        .chart {{ flex: 1; }}
        .bar {{ display: flex; align-items: center; margin: 5px 0; }}
        .bar-label {{ width: 150px; font-size: 12px; }}
        .bar-value {{ height: 20px; background: #667eea; border-radius: 3px; }}
        .bar-count {{ margin-left: 10px; font-size: 12px; color: #666; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; margin: 0 5px; }}
        .badge-json {{ background: #e3f2fd; color: #1976d2; }}
        .badge-media {{ background: #fce4ec; color: #c2185b; }}
        .footer {{ text-align: center; padding: 20px; color: #666; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎨 ComfyUI 工作流综合分析报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="container">
        <!-- 总体统计 -->
        <div class="section">
            <h2>📊 总体统计</h2>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-number">{stats.get('total_workflows', 0)}</div>
                    <div class="stat-label">工作流总数</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{stats.get('total_nodes', 0)}</div>
                    <div class="stat-label">节点总数</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{stats.get('total_model_references', 0)}</div>
                    <div class="stat-label">模型引用总数</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{stats.get('total_media_mappings', 0)}</div>
                    <div class="stat-label">媒体映射总数</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{stats.get('unique_workflow_hashes', 0)}</div>
                    <div class="stat-label">唯一工作流数</div>
                </div>
            </div>
        </div>

        <!-- 热门节点 -->
        <div class="section">
            <h2>🏆 热门节点排行 (Top 50)</h2>
            <table>
                <tr><th>排名</th><th>节点类型</th><th>使用次数</th><th>占比</th></tr>
"""

    total_nodes = stats.get('total_nodes', 1)
    for i, (node_type, count) in enumerate(top_nodes, 1):
        pct = count / total_nodes * 100
        html += f"<tr><td>{i}</td><td>{node_type}</td><td>{count}</td><td>{pct:.1f}%</td></tr>\n"

    html += """
            </table>
        </div>

        <!-- 热门模型 -->
        <div class="section">
            <h2>🔧 热门模型排行 (Top 50)</h2>
            <table>
                <tr><th>排名</th><th>模型类型</th><th>模型名称</th><th>引用次数</th></tr>
"""

    for i, (model_type, model_name, count) in enumerate(top_models, 1):
        html += f"<tr><td>{i}</td><td>{model_type}</td><td>{model_name}</td><td>{count}</td></tr>\n"

    html += """
            </table>
        </div>

        <!-- 模型类型分布 -->
        <div class="section">
            <h2>📦 模型类型分布</h2>
            <div class="chart-container">
"""

    max_model_count = max(m[1] for m in model_types) if model_types else 1
    for model_type, count in model_types:
        width = (count / max_model_count) * 300
        html += f"""
                <div class="bar">
                    <div class="bar-label">{model_type}</div>
                    <div class="bar-value" style="width: {width}px;"></div>
                    <div class="bar-count">{count}</div>
                </div>
"""

    html += """
            </div>
        </div>

        <!-- 工作流复杂度分布 -->
        <div class="section">
            <h2>📈 工作流复杂度分布</h2>
            <table>
                <tr><th>复杂度等级</th><th>数量</th><th>占比</th></tr>
"""

    total_wf = stats.get('total_workflows', 1)
    for category, count in complexity:
        pct = count / total_wf * 100
        html += f"<tr><td>{category}</td><td>{count}</td><td>{pct:.1f}%</td></tr>\n"

    html += """
            </table>
        </div>

        <!-- 最近添加的工作流 -->
        <div class="section">
            <h2>🕐 最近添加的工作流</h2>
            <table>
                <tr><th>文件名</th><th>来源</th><th>节点数</th><th>连接数</th><th>添加时间</th></tr>
"""

    for filename, source, node_count, link_count, created_at in recent_workflows:
        badge_class = 'badge-json' if source == 'json' else 'badge-media'
        html += f"<tr><td>{filename}</td><td><span class='badge {badge_class}'>{source}</span></td><td>{node_count}</td><td>{link_count}</td><td>{created_at}</td></tr>\n"

    html += """
            </table>
        </div>
    </div>

    <div class="footer">
        <p>ComfyUI Workflows Comprehensive Report</p>
        <p>数据来源: comfyui_workflows.db</p>
    </div>
</body>
</html>
"""

    output_path = OUTPUT_DIR / 'comprehensive_report.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def generate_excel_report():
    """生成Excel兼容的CSV报告集"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    reports = []

    # 1. 工作流列表
    cursor.execute('''
        SELECT filename, source, node_count, link_count, workflow_hash, created_at
        FROM workflows ORDER BY node_count DESC
    ''')
    workflows = cursor.fetchall()

    wf_csv = OUTPUT_DIR / 'report_workflows.csv'
    with open(wf_csv, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('文件名,来源,节点数,连接数,哈希值,添加时间\n')
        for row in workflows:
            f.write(','.join(str(v) for v in row) + '\n')
    reports.append(wf_csv)

    # 2. 节点统计
    cursor.execute('''
        SELECT node_type, COUNT(*) as cnt
        FROM nodes GROUP BY node_type ORDER BY cnt DESC
    ''')
    nodes = cursor.fetchall()

    nodes_csv = OUTPUT_DIR / 'report_nodes.csv'
    with open(nodes_csv, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('节点类型,使用次数,占比\n')
        total_nodes = sum(n[1] for n in nodes)
        for node_type, count in nodes:
            pct = count / total_nodes * 100 if total_nodes > 0 else 0
            f.write(f'{node_type},{count},{pct:.2f}%\n')
    reports.append(nodes_csv)

    # 3. 模型引用
    cursor.execute('''
        SELECT model_type, model_name, COUNT(*) as cnt
        FROM model_references
        GROUP BY model_type, model_name
        ORDER BY model_type, cnt DESC
    ''')
    models = cursor.fetchall()

    models_csv = OUTPUT_DIR / 'report_models.csv'
    with open(models_csv, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('模型类型,模型名称,引用次数\n')
        for row in models:
            f.write(','.join(str(v) for v in row) + '\n')
    reports.append(models_csv)

    # 4. 媒体映射
    cursor.execute('''
        SELECT media_file, workflow_json, workflow_hash, is_duplicate, media_type, node_count
        FROM media_mappings
    ''')
    mappings = cursor.fetchall()

    mapping_csv = OUTPUT_DIR / 'report_media_mapping.csv'
    with open(mapping_csv, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('媒体文件,工作流JSON,哈希值,是否重复,媒体类型,节点数\n')
        for row in mappings:
            f.write(','.join(str(v) for v in row) + '\n')
    reports.append(mapping_csv)

    conn.close()
    return reports


def main():
    print("=" * 60)
    print("ComfyUI 工作流报告导出工具")
    print("=" * 60)

    if not DB_PATH.exists():
        print("\n错误: 数据库文件不存在")
        print("请先运行: python database_manager.py")
        return

    # 生成HTML报告
    print("\n[1] 生成综合HTML报告...")
    html_path = generate_comprehensive_html_report()
    print(f"  输出: {html_path}")

    # 生成Excel CSV报告
    print("\n[2] 生成Excel CSV报告...")
    csv_reports = generate_excel_report()
    for csv_path in csv_reports:
        print(f"  输出: {csv_path}")

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)

    print("\n💡 报告说明:")
    print("  - comprehensive_report.html: 综合分析HTML报告")
    print("  - report_workflows.csv: 工作流列表")
    print("  - report_nodes.csv: 节点统计")
    print("  - report_models.csv: 模型引用统计")
    print("  - report_media_mapping.csv: 媒体映射表")


if __name__ == "__main__":
    main()