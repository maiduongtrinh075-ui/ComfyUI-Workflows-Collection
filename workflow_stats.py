#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流统计分析工具
统计常用节点排行、节点组合模式、工作流复杂度分布
"""

import json
import sys
import csv
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 目录配置
JSON_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_JSON")
MEDIA_JSON_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets/Workflows_JSON_From_Media")
OUTPUT_DIR = Path("F:/ComfyuiCatchJson/Extracted_ComfyUI_Assets")

def load_workflows():
    """加载所有工作流"""
    workflows = []

    # 加载JSON工作流
    for f in JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(f, encoding='utf-8'))
            workflows.append({
                'source': f.name,
                'type': 'json',
                'data': data
            })
        except:
            pass

    # 加载媒体提取的工作流
    for f in MEDIA_JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(f, encoding='utf-8'))
            workflows.append({
                'source': f.name,
                'type': 'media',
                'data': data
            })
        except:
            pass

    return workflows


def extract_nodes(workflow_data):
    """从工作流中提取节点信息"""
    nodes = []

    # 标准 nodes/links 格式
    if 'nodes' in workflow_data:
        for node in workflow_data.get('nodes', []):
            node_type = node.get('type', '')
            if node_type:
                nodes.append(node_type)

    # API格式 (节点ID作为键)
    else:
        for key, node in workflow_data.items():
            if isinstance(node, dict) and 'class_type' in node:
                nodes.append(node['class_type'])

    return nodes


def analyze_node_frequency(workflows):
    """统计节点频率"""
    node_counter = Counter()

    for wf in workflows:
        nodes = extract_nodes(wf['data'])
        node_counter.update(nodes)

    return node_counter


def analyze_node_combinations(workflows, top_n=50):
    """统计常见节点组合（2节点组合）"""
    combo_counter = Counter()

    for wf in workflows:
        nodes = extract_nodes(wf['data'])
        unique_nodes = sorted(set(nodes))

        # 统计2节点组合
        for combo in combinations(unique_nodes[:20], 2):  # 只取前20个节点避免组合爆炸
            combo_counter.update([tuple(sorted(combo))])

    return combo_counter.most_common(top_n)


def analyze_complexity(workflows):
    """分析工作流复杂度"""
    complexity_stats = {
        'node_counts': [],
        'link_counts': [],
        'by_category': defaultdict(list)
    }

    for wf in workflows:
        data = wf['data']

        # 节点数
        if 'nodes' in data:
            node_count = len(data.get('nodes', []))
            link_count = len(data.get('links', []))
        else:
            node_count = len(data)
            link_count = 0  # API格式没有显式links

        complexity_stats['node_counts'].append(node_count)
        complexity_stats['link_counts'].append(link_count)

        # 按节点数分类
        if node_count < 20:
            complexity_stats['by_category']['简单(<20节点)'].append(wf['source'])
        elif node_count < 50:
            complexity_stats['by_category']['中等(20-50节点)'].append(wf['source'])
        elif node_count < 100:
            complexity_stats['by_category']['复杂(50-100节点)'].append(wf['source'])
        else:
            complexity_stats['by_category']['超复杂(>100节点)'].append(wf['source'])

    return complexity_stats


def generate_report(node_freq, node_combos, complexity, output_path):
    """生成HTML报告"""
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ComfyUI 工作流统计分析报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #4CAF50; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
        .stat-box { background: #e8f5e9; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .chart { margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ComfyUI 工作流统计分析报告</h1>

        <div class="stat-box">
            <h2>📊 总体统计</h2>
            <p><strong>工作流总数:</strong> """ + str(len(complexity['node_counts'])) + """</p>
            <p><strong>平均节点数:</strong> """ + str(sum(complexity['node_counts'])//len(complexity['node_counts']) if complexity['node_counts'] else 0) + """</p>
            <p><strong>唯一节点类型:</strong> """ + str(len(node_freq)) + """</p>
        </div>

        <h2>🏆 热门节点排行 (Top 50)</h2>
        <table>
            <tr><th>排名</th><th>节点类型</th><th>使用次数</th><th>占比</th></tr>
"""

    total_usage = sum(node_freq.values())
    for i, (node, count) in enumerate(node_freq.most_common(50), 1):
        pct = count / total_usage * 100 if total_usage > 0 else 0
        html += f"<tr><td>{i}</td><td>{node}</td><td>{count}</td><td>{pct:.1f}%</td></tr>\n"

    html += """
        </table>

        <h2>🔗 常见节点组合 (Top 30)</h2>
        <table>
            <tr><th>排名</th><th>节点组合</th><th>出现次数</th></tr>
"""

    for i, (combo, count) in enumerate(node_combos[:30], 1):
        combo_str = f"{combo[0]} + {combo[1]}"
        html += f"<tr><td>{i}</td><td>{combo_str}</td><td>{count}</td></tr>\n"

    html += """
        </table>

        <h2>📈 工作流复杂度分布</h2>
        <table>
            <tr><th>复杂度等级</th><th>数量</th><th>占比</th></tr>
"""

    total_workflows = len(complexity['node_counts'])
    for category, files in complexity['by_category'].items():
        pct = len(files) / total_workflows * 100 if total_workflows > 0 else 0
        html += f"<tr><td>{category}</td><td>{len(files)}</td><td>{pct:.1f}%</td></tr>\n"

    html += """
        </table>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def export_csv_reports(node_freq, node_combos, complexity, output_dir):
    """导出CSV报告"""

    # 节点频率CSV
    nodes_csv = output_dir / 'node_frequency.csv'
    with open(nodes_csv, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['节点类型', '使用次数', '占比'])
        total = sum(node_freq.values())
        for node, count in node_freq.most_common():
            pct = count / total * 100 if total > 0 else 0
            writer.writerow([node, count, f'{pct:.2f}%'])

    print(f"  节点频率CSV: {nodes_csv}")


def main():
    print("=" * 60)
    print("工作流统计分析工具")
    print("=" * 60)

    # 加载工作流
    print("\n加载工作流...")
    workflows = load_workflows()
    print(f"  加载 {len(workflows)} 个工作流")

    # 分析节点频率
    print("\n分析节点频率...")
    node_freq = analyze_node_frequency(workflows)
    print(f"  发现 {len(node_freq)} 种节点类型")
    print(f"  最常用节点: {node_freq.most_common(5)}")

    # 分析节点组合
    print("\n分析节点组合...")
    node_combos = analyze_node_combinations(workflows)
    print(f"  分析完成，Top 5 组合: {node_combos[:5]}")

    # 分析复杂度
    print("\n分析复杂度...")
    complexity = analyze_complexity(workflows)
    for cat, files in complexity['by_category'].items():
        print(f"  {cat}: {len(files)} 个")

    # 生成报告
    print("\n生成报告...")
    html_path = OUTPUT_DIR / 'workflow_stats_report.html'
    generate_report(node_freq, node_combos, complexity, html_path)
    print(f"  HTML报告: {html_path}")

    # 导出CSV
    print("\n导出CSV...")
    export_csv_reports(node_freq, node_combos, complexity, OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("完成!")
    print(f"请打开: {html_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()