#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Release 发布脚本
创建tag并推送，触发GitHub Actions自动构建Windows/Mac版本
"""

import subprocess
import sys
from pathlib import Path

def get_current_version():
    """获取当前版本（从git tags）"""
    result = subprocess.run(
        ['git', 'tag', '--sort=-v:refname'],
        capture_output=True, text=True
    )
    tags = result.stdout.strip().split('\n')
    if tags and tags[0]:
        # 解析最新版本号
        latest = tags[0]
        if latest.startswith('v'):
            parts = latest[1:].split('.')
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
    return 0, 0

def create_release():
    """创建新版本发布"""
    print("=" * 60)
    print("GitHub Release 发布脚本")
    print("=" * 60)

    # 检查是否有未提交的更改
    result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
    if result.stdout.strip():
        print("\n⚠️ 检测到未提交的更改:")
        print(result.stdout)
        print("\n请先提交所有更改后再发布!")
        return

    # 获取当前版本
    major, minor = get_current_version()
    new_version = f"v{major}.{minor + 1}"

    print(f"\n当前最新版本: v{major}.{minor}")
    print(f"新版本号: {new_version}")

    # 让用户确认
    confirm = input("\n确认发布此版本? (y/n): ").strip().lower()
    if confirm != 'y':
        print("取消发布")
        return

    # 检查远程状态
    print("\n[1] 检查远程仓库...")
    result = subprocess.run(['git', 'fetch'], capture_output=True, text=True)
    if result.returncode != 0:
        print("同步远程仓库失败")
        return

    result = subprocess.run(['git', 'status'], capture_output=True, text=True)
    if 'behind' in result.stdout:
        print("⚠️ 本地分支落后于远程，请先 git pull")
        return

    # 创建tag
    print(f"\n[2] 创建tag: {new_version}")
    result = subprocess.run(['git', 'tag', '-a', new_version, '-m', f'Release {new_version}'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"创建tag失败: {result.stderr}")
        return

    # 推送tag
    print(f"\n[3] 推送tag到远程...")
    result = subprocess.run(['git', 'push', 'origin', new_version], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"推送tag失败: {result.stderr}")
        return

    print("\n" + "=" * 60)
    print("✓ 发布成功!")
    print("=" * 60)

    print(f"\nTag已推送: {new_version}")
    print("GitHub Actions将自动构建:")
    print("  - Windows: ComfyUI-Tool.exe")
    print("  - macOS: ComfyUI-Tool")

    print("\n查看构建进度:")
    print("  https://github.com/maiduongtrinh075-ui/ComfyUI-Workflows-Collection/actions")

    print("\n构建完成后，Release页面:")
    print("  https://github.com/maiduongtrinh075-ui/ComfyUI-Workflows-Collection/releases")


def show_help():
    """显示帮助信息"""
    print("""
使用方法:
  python release.py              创建并发布新版本
  python release.py --help       显示帮助信息

发布流程:
  1. 确保所有更改已提交并推送
  2. 运行脚本创建新版本tag
  3. 推送tag触发GitHub Actions
  4. 自动构建Windows/Mac可执行文件
  5. 发布到GitHub Releases页面

版本号规则:
  - 自动递增minor版本号 (如 v1.0 → v1.1)
  - 如需修改major版本，请手动创建tag: git tag v2.0

手动操作:
  git tag -a v1.0 -m "Release 1.0"    # 创建tag
  git push origin v1.0                 # 推送tag
  git tag -d v1.0                      # 删除本地tag
  git push origin --delete v1.0        # 删除远程tag
""")


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        show_help()
    else:
        create_release()


if __name__ == "__main__":
    main()