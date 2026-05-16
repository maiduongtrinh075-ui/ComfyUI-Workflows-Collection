#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QCE (QQ Chat Exporter) API 调用模块
整合 NapCat + QCE 工具到 ComfyUI 工作流提取项目
"""

import subprocess
import time
import json
import requests
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# QCE 目录路径
QCE_DIR = Path(__file__).parent / 'qq-chat-exporter'
NAPI_LOADER = QCE_DIR / 'napiLoader.bat'

# API 配置
API_HOST = 'localhost'
API_PORT = 40653
WEBUI_PORT = 6099
API_BASE = f'http://{API_HOST}:{API_PORT}'

# Token 存储路径
SECURITY_FILE = Path(os.environ.get('USERPROFILE', '')) / '.qq-chat-exporter' / 'security.json'


class QCEProcess:
    """管理 QCE 进程生命周期"""

    def __init__(self, qce_dir: Optional[Path] = None):
        self.qce_dir = qce_dir or QCE_DIR
        self.napi_loader = self.qce_dir / 'napiLoader.bat'
        self.process: Optional[subprocess.Popen] = None
        self.running = False

    def start(self) -> bool:
        """启动 QCE 进程"""
        if not self.napi_loader.exists():
            print(f"错误: 未找到 napiLoader.bat: {self.napi_loader}")
            return False

        print(f"启动 QCE...")
        print(f"目录: {self.qce_dir}")

        # 使用 subprocess 启动批处理文件
        self.process = subprocess.Popen(
            ['cmd', '/c', str(self.napi_loader)],
            cwd=str(self.qce_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

        self.running = True
        print(f"进程已启动 (PID: {self.process.pid})")
        return True

    def wait_ready(self, timeout: int = 60) -> bool:
        """等待 API 服务就绪"""
        print(f"等待 API 服务就绪 (最多 {timeout} 秒)...")

        client = QCEClient()
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 尝试连接 API
                response = requests.get(f'{API_BASE}/api/status', timeout=2)
                if response.status_code == 200:
                    print("API 服务已就绪!")
                    return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(2)

        print("等待超时，API 服务未就绪")
        return False

    def stop(self):
        """停止 QCE 进程"""
        if self.process and self.running:
            print("停止 QCE 进程...")
            self.process.terminate()
            self.process.wait(timeout=5)
            self.running = False
            print("进程已停止")

    def is_running(self) -> bool:
        """检查进程是否仍在运行"""
        if self.process:
            return self.process.poll() is None
        return False


class QCEClient:
    """QCE REST API 调用封装"""

    def __init__(self, token: Optional[str] = None, host: str = API_HOST, port: int = API_PORT):
        self.base_url = f'http://{host}:{port}'
        self.token = token or self._get_token()

    def _get_token(self) -> str:
        """从 security.json 获取 token"""
        # 首先尝试从文件读取
        if SECURITY_FILE.exists():
            try:
                with open(SECURITY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('accessToken', '')
            except Exception:
                pass

        # 其次从 webui.json 获取默认 token
        webui_config = QCE_DIR / 'config' / 'webui.json'
        if webui_config.exists():
            try:
                with open(webui_config, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('token', '')
            except Exception:
                pass

        return ''

    def _request(self, endpoint: str, method: str = 'GET', data: Optional[Dict] = None) -> Optional[Dict]:
        """发送 API 请求"""
        url = f'{self.base_url}{endpoint}'
        headers = {'Authorization': f'Bearer {self.token}'}

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=60)
            else:
                return None

            if response.status_code == 200:
                return response.json()
            else:
                print(f"API 错误: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None

    def get_status(self) -> Optional[Dict]:
        """获取 API 状态"""
        return self._request('/api/status')

    def get_groups(self) -> List[Dict]:
        """获取群聊列表"""
        result = self._request('/api/groups')
        return result.get('data', []) if result else []

    def get_friends(self) -> List[Dict]:
        """获取好友列表"""
        result = self._request('/api/friends')
        return result.get('data', []) if result else []

    def get_chat_messages(self, chat_type: str, chat_id: str, count: int = 100) -> Optional[Dict]:
        """获取聊天消息"""
        data = {
            'chatType': chat_type,  # 'group' 或 'friend'
            'chatId': chat_id,
            'count': count
        }
        return self._request('/api/messages/fetch', method='POST', data=data)

    def export_chat(self, chat_type: str, chat_id: str, format: str = 'json',
                    output_dir: Optional[str] = None) -> Optional[str]:
        """
        导出聊天记录

        Args:
            chat_type: 'group' 或 'friend'
            chat_id: 群号或好友ID
            format: 导出格式 (json, excel, html, text)
            output_dir: 输出目录

        Returns:
            导出文件路径或 None
        """
        data = {
            'chatType': chat_type,
            'chatId': chat_id,
            'format': format,
            'outputDir': output_dir
        }

        result = self._request('/api/messages/export', method='POST', data=data)

        if result and result.get('success'):
            return result.get('filePath')
        return None

    def list_chats(self) -> Dict[str, List[Dict]]:
        """列出所有可导出的聊天"""
        return {
            'groups': self.get_groups(),
            'friends': self.get_friends()
        }

    def print_info(self):
        """打印连接信息"""
        print("=" * 50)
        print("QCE API 连接信息")
        print("=" * 50)
        print(f"API 地址: {self.base_url}")
        print(f"Web UI: http://localhost:{WEBUI_PORT}/qce-v4-tool")
        print(f"Token: {self.token}")
        print("=" * 50)


def interactive_export():
    """交互式导出聊天记录"""
    client = QCEClient()
    client.print_info()

    # 测试连接
    status = client.get_status()
    if not status:
        print("无法连接到 QCE API，请确认 QCE 已启动")
        return

    print("\n连接成功!")
    print("\n正在获取聊天列表...")

    chats = client.list_chats()

    groups = chats.get('groups', [])
    friends = chats.get('friends', [])

    print(f"\n群聊: {len(groups)} 个")
    print(f"好友: {len(friends)} 个")

    if groups:
        print("\n群聊列表:")
        for i, group in enumerate(groups[:20], 1):  # 只显示前20个
            name = group.get('groupName', group.get('name', '未知'))
            id = group.get('groupId', group.get('id', ''))
            print(f"  {i}. {name} ({id})")

    if friends:
        print("\n好友列表:")
        for i, friend in enumerate(friends[:20], 1):  # 只显示前20个
            name = friend.get('friendName', friend.get('name', '未知'))
            id = friend.get('friendId', friend.get('id', ''))
            print(f"  {i}. {name} ({id})")

    # 导出选项
    print("\n" + "=" * 50)
    print("导出选项:")
    print("  1. 导出所有群聊")
    print("  2. 导出所有好友聊天")
    print("  3. 导出指定聊天")
    print("  4. 查看更多聊天")
    print("  0. 退出")
    print("=" * 50)

    choice = input("请选择 (0-4): ").strip()

    if choice == '0':
        return
    elif choice == '1':
        # 导出所有群聊
        output_dir = input("输出目录 (默认 ./QCE_Export): ").strip() or './QCE_Export'
        Path(output_dir).mkdir(exist_ok=True)

        print(f"\n开始导出 {len(groups)} 个群聊...")
        for i, group in enumerate(groups, 1):
            name = group.get('groupName', group.get('name', '未知'))
            id = group.get('groupId', group.get('id', ''))
            print(f"[{i}/{len(groups)}] 导出: {name}")
            result = client.export_chat('group', id, 'json', output_dir)
            if result:
                print(f"  ✓ {result}")
            else:
                print(f"  ✗ 导出失败")

    elif choice == '2':
        # 导出所有好友聊天
        output_dir = input("输出目录 (默认 ./QCE_Export): ").strip() or './QCE_Export'
        Path(output_dir).mkdir(exist_ok=True)

        print(f"\n开始导出 {len(friends)} 个好友聊天...")
        for i, friend in enumerate(friends, 1):
            name = friend.get('friendName', friend.get('name', '未知'))
            id = friend.get('friendId', friend.get('id', ''))
            print(f"[{i}/{len(friends)}] 导出: {name}")
            result = client.export_chat('friend', id, 'json', output_dir)
            if result:
                print(f"  ✓ {result}")
            else:
                print(f"  ✗ 导出失败")

    elif choice == '3':
        # 导出指定聊天
        chat_type = input("聊天类型 (group/friend): ").strip()
        chat_id = input("聊天ID: ").strip()
        output_dir = input("输出目录 (默认 ./QCE_Export): ").strip() or './QCE_Export'
        Path(output_dir).mkdir(exist_ok=True)

        print(f"\n开始导出...")
        result = client.export_chat(chat_type, chat_id, 'json', output_dir)
        if result:
            print(f"✓ 导出成功: {result}")
        else:
            print("✗ 导出失败")


def test_connection():
    """测试 API 连接"""
    print("测试 QCE API 连接...")

    client = QCEClient()
    client.print_info()

    status = client.get_status()

    if status:
        print("\n✓ 连接成功!")
        print(f"状态: {json.dumps(status, indent=2, ensure_ascii=False)}")

        # 测试获取聊天列表
        chats = client.list_chats()
        print(f"\n群聊数量: {len(chats.get('groups', []))}")
        print(f"好友数量: {len(chats.get('friends', []))}")
    else:
        print("\n✗ 连接失败")
        print("请确认:")
        print("  1. QCE 已启动 (运行 python start_qce.py)")
        print("  2. QQ 已登录")
        print("  3. API 服务正常运行")


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description='QCE API 调用工具')
    parser.add_argument('--start', action='store_true', help='启动 QCE 进程')
    parser.add_argument('--test', action='store_true', help='测试 API 连接')
    parser.add_argument('--export', action='store_true', help='交互式导出聊天记录')
    parser.add_argument('--status', action='store_true', help='获取 API 状态')
    parser.add_argument('--list', action='store_true', help='列出所有聊天')
    parser.add_argument('--groups', action='store_true', help='列出群聊')
    parser.add_argument('--friends', action='store_true', help='列出好友')

    args = parser.parse_args()

    if args.start:
        proc = QCEProcess()
        proc.start()
        if proc.wait_ready():
            print("\nQCE 已就绪，可以开始导出聊天记录")
            print("运行: python qce_api.py --export")
            print("Web UI: http://localhost:6099/qce-v4-tool")
            input("\n按回车键退出...")
        proc.stop()
    elif args.test:
        test_connection()
    elif args.export:
        interactive_export()
    elif args.status:
        client = QCEClient()
        status = client.get_status()
        if status:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print("获取状态失败")
    elif args.list or args.groups or args.friends:
        client = QCEClient()
        chats = client.list_chats()

        if args.list or args.groups:
            groups = chats.get('groups', [])
            print(f"群聊 ({len(groups)} 个):")
            for group in groups:
                name = group.get('groupName', group.get('name', '未知'))
                id = group.get('groupId', group.get('id', ''))
                print(f"  {name} ({id})")

        if args.list or args.friends:
            friends = chats.get('friends', [])
            print(f"\n好友 ({len(friends)} 个):")
            for friend in friends:
                name = friend.get('friendName', friend.get('name', '未知'))
                id = friend.get('friendId', friend.get('id', ''))
                print(f"  {name} ({id})")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()