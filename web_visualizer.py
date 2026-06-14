#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 工作流 Web 可视化工具
提供Web界面查看工作流、搜索模型、查看统计报告
"""

import json
import sys
import os
import csv
import hashlib
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 目录配置（统一从 paths 模块取）
from paths import (  # noqa: E402
    OUTPUT_DIR as BASE_DIR,
    WORKFLOWS_JSON_DIR as JSON_DIR,
    WORKFLOWS_JSON_FROM_MEDIA_DIR as MEDIA_JSON_DIR,
    WORKFLOWS_MEDIA_DIR as MEDIA_DIR,
    MEDIA_WORKFLOW_MAPPING_FILE as MAPPING_FILE,
    MODEL_RESOURCES_CSV as MODEL_CSV,
    WORKFLOW_STATS_REPORT_HTML as STATS_HTML,
    MISSING_MODELS_REPORT_HTML as MISSING_HTML,
)

# Web服务器配置
PORT = 8080
HOST = "localhost"


def load_all_workflows():
    """加载所有工作流数据"""
    workflows = []

    # 加载JSON目录的工作流
    for json_file in JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(json_file, encoding='utf-8'))
            workflows.append({
                'id': json_file.stem,
                'filename': json_file.name,
                'source': 'json',
                'node_count': len(data.get('nodes', data.keys())),
                'data': data
            })
        except:
            pass

    # 加载媒体提取的工作流
    for json_file in MEDIA_JSON_DIR.glob('*.json'):
        try:
            data = json.load(open(json_file, encoding='utf-8'))
            workflows.append({
                'id': json_file.stem,
                'filename': json_file.name,
                'source': 'media',
                'node_count': len(data.get('nodes', data.keys())),
                'data': data
            })
        except:
            pass

    return workflows


def load_model_resources():
    """加载模型资源CSV"""
    models = []
    if MODEL_CSV.exists():
        with open(MODEL_CSV, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                models.append(row)
    return models


def load_media_mapping():
    """加载媒体映射表"""
    if MAPPING_FILE.exists():
        return json.load(open(MAPPING_FILE, encoding='utf-8'))
    return {'mappings': []}


def extract_nodes_from_workflow(workflow_data):
    """从工作流提取节点类型"""
    nodes = []

    if 'nodes' in workflow_data:
        for node in workflow_data.get('nodes', []):
            node_type = node.get('type', '')
            if node_type:
                nodes.append(node_type)
    else:
        for key, node in workflow_data.items():
            if isinstance(node, dict) and 'class_type' in node:
                nodes.append(node['class_type'])

    return nodes


def search_workflows(query, search_type='node'):
    """搜索工作流"""
    workflows = load_all_workflows()
    results = []

    query_lower = query.lower()

    for wf in workflows:
        nodes = extract_nodes_from_workflow(wf['data'])

        if search_type == 'node':
            # 搜索节点类型
            if any(query_lower in node.lower() for node in nodes):
                results.append({
                    'filename': wf['filename'],
                    'source': wf['source'],
                    'node_count': wf['node_count'],
                    'matched_nodes': [n for n in nodes if query_lower in n.lower()]
                })

        elif search_type == 'model':
            # 搜索模型名称（在widgets_values中）
            found_models = []
            if 'nodes' in wf['data']:
                for node in wf['data'].get('nodes', []):
                    for val in node.get('widgets_values', []):
                        if isinstance(val, str) and query_lower in val.lower():
                            if any(ext in val.lower() for ext in ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']):
                                found_models.append(val)

            if found_models:
                results.append({
                    'filename': wf['filename'],
                    'source': wf['source'],
                    'node_count': wf['node_count'],
                    'matched_models': found_models
                })

    return results


class WebHandler(SimpleHTTPRequestHandler):
    """自定义HTTP请求处理器"""

    def __init__(self, *args, **kwargs):
        self.base_dir = BASE_DIR
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API路由
        if path == '/api/workflows':
            self.handle_api_workflows()

        elif path == '/api/search':
            q = query.get('q', [''])[0]
            type_ = query.get('type', ['node'])[0]
            self.handle_api_search(q, type_)

        elif path == '/api/models':
            self.handle_api_models()

        elif path == '/api/media_mapping':
            self.handle_api_media_mapping()

        elif path == '/api/workflow_detail':
            filename = query.get('file', [''])[0]
            self.handle_api_workflow_detail(filename)

        elif path == '/':
            self.handle_index()

        elif path == '/stats':
            self.handle_stats()

        elif path == '/missing':
            self.handle_missing()

        else:
            super().do_GET()

    def send_json(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_html(self, html):
        """发送HTML响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_index(self):
        """主页"""
        workflows = load_all_workflows()
        models = load_model_resources()
        mapping = load_media_mapping()

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ComfyUI 工作流可视化</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; }
        .header h1 { font-size: 24px; margin-bottom: 10px; }
        .nav { display: flex; gap: 15px; margin-top: 10px; }
        .nav a { color: white; text-decoration: none; padding: 8px 15px; background: rgba(255,255,255,0.2); border-radius: 5px; }
        .nav a:hover { background: rgba(255,255,255,0.3); }
        .container { max-width: 1400px; margin: 20px auto; padding: 20px; }
        .search-box { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .search-input { width: 300px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
        .search-btn { padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; }
        .stats-row { display: flex; gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; flex: 1; }
        .stat-card h3 { color: #667eea; margin-bottom: 10px; }
        .stat-number { font-size: 36px; font-weight: bold; color: #333; }
        .workflows-list { background: white; border-radius: 10px; padding: 20px; }
        .workflows-list h2 { margin-bottom: 15px; color: #333; }
        .workflow-item { padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; }
        .workflow-item:hover { background: #f5f5f5; }
        .workflow-name { font-weight: bold; }
        .workflow-meta { color: #666; font-size: 12px; }
        .results { background: white; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .result-item { padding: 10px; border-bottom: 1px solid #eee; }
        .matched { color: #667eea; font-weight: bold; }
        .footer { text-align: center; padding: 20px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎨 ComfyUI 工作流可视化工具</h1>
        <div class="nav">
            <a href="/">首页</a>
            <a href="/stats">统计报告</a>
            <a href="/missing">缺失模型</a>
        </div>
    </div>

    <div class="container">
        <div class="search-box">
            <h3>🔍 搜索工作流</h3>
            <input type="text" id="searchQuery" class="search-input" placeholder="输入节点名称或模型名称...">
            <select id="searchType" style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                <option value="node">节点类型</option>
                <option value="model">模型名称</option>
            </select>
            <button class="search-btn" onclick="search()">搜索</button>
        </div>

        <div class="stats-row">
            <div class="stat-card">
                <h3>📁 工作流总数</h3>
                <div class="stat-number">{len(workflows)}</div>
            </div>
            <div class="stat-card">
                <h3>🔧 模型资源</h3>
                <div class="stat-number">{len(models)}</div>
            </div>
            <div class="stat-card">
                <h3>📸 媒体文件</h3>
                <div class="stat-number">{mapping.get('total_media_files', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>🎯 唯一工作流</h3>
                <div class="stat-number">{mapping.get('unique_workflows', 0)}</div>
            </div>
        </div>

        <div id="results" class="results" style="display:none;"></div>

        <div class="workflows-list">
            <h2>📋 最近的工作流文件</h2>
            <div id="workflowsList">
"""

        # 显示前20个工作流
        for wf in workflows[:20]:
            html += f"""
                <div class="workflow-item" onclick="showWorkflow('{wf['filename']}')">
                    <div class="workflow-name">{wf['filename']}</div>
                    <div class="workflow-meta">节点数: {wf['node_count']} | 来源: {wf['source']}</div>
                </div>
"""

        html += """
            </div>
            <p style="text-align:center; color:#666; margin-top:10px;">显示前20个，共 <span id="totalCount"></span> 个工作流</p>
        </div>
    </div>

    <div class="footer">
        <p>ComfyUI Workflows Visualization Tool</p>
    </div>

    <script>
        document.getElementById('totalCount').textContent = '""" + str(len(workflows)) + """';

        function search() {
            const query = document.getElementById('searchQuery').value;
            const type = document.getElementById('searchType').value;

            if (!query) return;

            fetch(`/api/search?q=${encodeURIComponent(query)}&type=${type}`)
                .then(r => r.json())
                .then(data => {
                    const resultsDiv = document.getElementById('results');
                    resultsDiv.style.display = 'block';

                    if (data.length === 0) {
                        resultsDiv.innerHTML = '<p>未找到匹配结果</p>';
                        return;
                    }

                    let html = '<h3>搜索结果 (' + data.length + ')</h3>';
                    data.forEach(item => {
                        html += '<div class="result-item">';
                        html += '<div class="workflow-name">' + item.filename + '</div>';
                        html += '<div class="workflow-meta">节点数: ' + item.node_count + '</div>';

                        if (item.matched_nodes) {
                            html += '<div class="matched">匹配节点: ' + item.matched_nodes.join(', ') + '</div>';
                        }
                        if (item.matched_models) {
                            html += '<div class="matched">匹配模型: ' + item.matched_models.join(', ') + '</div>';
                        }
                        html += '</div>';
                    });

                    resultsDiv.innerHTML = html;
                });
        }

        function showWorkflow(filename) {
            window.location.href = `/api/workflow_detail?file=${encodeURIComponent(filename)}`;
        }
    </script>
</body>
</html>
"""
        self.send_html(html)

    def handle_stats(self):
        """统计报告页面"""
        if STATS_HTML.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(open(STATS_HTML, 'r', encoding='utf-8').read().encode('utf-8'))
        else:
            self.send_html("<h1>统计报告尚未生成</h1><p>请先运行: python workflow_stats.py</p>")

    def handle_missing(self):
        """缺失模型页面"""
        if MISSING_HTML.exists():
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(open(MISSING_HTML, 'r', encoding='utf-8').read().encode('utf-8'))
        else:
            self.send_html("<h1>缺失模型报告尚未生成</h1><p>请先运行: python missing_model_detector.py</p>")

    def handle_api_workflows(self):
        """API: 获取工作流列表"""
        workflows = load_all_workflows()
        result = [{
            'filename': wf['filename'],
            'source': wf['source'],
            'node_count': wf['node_count']
        } for wf in workflows]
        self.send_json(result)

    def handle_api_search(self, query, search_type):
        """API: 搜索工作流"""
        if not query:
            self.send_json([])
            return
        results = search_workflows(query, search_type)
        self.send_json(results)

    def handle_api_models(self):
        """API: 获取模型列表"""
        models = load_model_resources()
        self.send_json(models)

    def handle_api_media_mapping(self):
        """API: 获取媒体映射"""
        mapping = load_media_mapping()
        self.send_json(mapping)

    def handle_api_workflow_detail(self, filename):
        """API: 获取工作流详情"""
        if not filename:
            self.send_json({'error': 'No filename provided'})
            return

        # 尝试在不同目录查找
        json_path = JSON_DIR / filename
        if not json_path.exists():
            json_path = MEDIA_JSON_DIR / filename

        if not json_path.exists():
            self.send_json({'error': 'File not found'})
            return

        try:
            data = json.load(open(json_path, encoding='utf-8'))
            nodes = extract_nodes_from_workflow(data)

            result = {
                'filename': filename,
                'node_count': len(nodes),
                'nodes': nodes,
                'data_preview': json.dumps(data, ensure_ascii=False, indent=2)[:5000]
            }
            self.send_json(result)
        except Exception as e:
            self.send_json({'error': str(e)})


def main():
    print("=" * 60)
    print("ComfyUI 工作流 Web 可视化工具")
    print("=" * 60)

    print(f"\n启动Web服务器...")
    print(f"地址: http://{HOST}:{PORT}")
    print(f"\n功能:")
    print(f"  - 查看所有工作流")
    print(f"  - 搜索节点类型/模型名称")
    print(f"  - 查看统计报告")
    print(f"  - 查看缺失模型报告")

    print(f"\n按 Ctrl+C 停止服务器")

    try:
        server = HTTPServer((HOST, PORT), WebHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"\n启动失败: {e}")


if __name__ == "__main__":
    main()