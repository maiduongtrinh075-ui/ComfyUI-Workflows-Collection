#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ComfyUI 工作流自动提取工具（增强版）
功能：扫描微信/腾讯软件缓存目录，提取ComfyUI工作流文件和压缩包
增强：支持视频文件、文件魔数检测（无视后缀名）、未知格式探测
作者：Claude Code
日期：2026-05-05
"""

import json
import logging
import shutil
import hashlib
import subprocess
import struct
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, Tuple, Set
from PIL import Image
import uuid

# 定期保存间隔（每处理多少个文件保存一次进度）
SAVE_INTERVAL = 500

# ==================== 配置区域 ====================

# 数据源路径清单：默认从 paths.SCAN_PATHS 读取（基于当前用户自动发现常见
# 微信/QQ/Downloads 目录）。可通过 user_config.json 的 scan_paths 字段覆盖。
from paths import SCAN_PATHS  # noqa: E402

# 压缩包扩展名
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz'}

# 图片扩展名（可能包含工作流元数据）
IMAGE_EXTENSIONS = {'.png', '.webp', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.apng'}

# 视频扩展名（可能包含工作流元数据）
VIDEO_EXTENSIONS = {'.mp4', '.webm', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.gifv'}

# 媒体扩展名合并
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

# JSON扩展名
JSON_EXTENSION = '.json'

# 最大尝试解析的文件大小（避免处理超大文件）
MAX_FILE_SIZE_TO_PARSE = 100 * 1024 * 1024  # 100MB

# 输出目录名称
OUTPUT_DIR_NAME = "Extracted_ComfyUI_Assets"
WORKFLOW_JSON_DIR = "Workflows_JSON"
WORKFLOW_MEDIA_DIR = "Workflows_Media"
WORKFLOW_UNKNOWN_DIR = "Workflows_Unknown"  # 新增：未知后缀的工作流
ARCHIVES_DIR = "Archives"

# 扫描历史记录文件
HISTORY_FILE = "scanned_history.json"

# 工作流映射记录文件（记录每个文件对应的工作流信息）
WORKFLOW_MAPPING_FILE = "workflow_mapping.json"

# 日志配置（强制使用 UTF-8 编码）
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ==================== 文件魔数检测 ====================

# 文件魔数签名表（文件头字节）
FILE_SIGNATURES = {
    # 图片格式
    b'\x89PNG\r\n\x1a\n': ('png', 'image/png'),
    b'\xff\xd8\xff': ('jpeg', 'image/jpeg'),
    b'GIF87a': ('gif', 'image/gif'),
    b'GIF89a': ('gif', 'image/gif'),
    b'RIFF': ('webp', 'image/webp'),  # WebP以RIFF开头，需进一步检查
    b'BM': ('bmp', 'image/bmp'),

    # 视频格式
    b'\x00\x00\x00\x1cftypisom': ('mp4', 'video/mp4'),
    b'\x00\x00\x00\x18ftypmp42': ('mp4', 'video/mp4'),
    b'\x00\x00\x00\x20ftypisom': ('mp4', 'video/mp4'),
    b'\x1aE\xdf\xa3': ('webm', 'video/webm'),  # WebM/MKV Matroska
    b'RIFFAVI': ('avi', 'video/avi'),

    # 压缩包格式
    b'PK\x03\x04': ('zip', 'application/zip'),
    b'Rar!\x1a\x07': ('rar', 'application/rar'),
    b'7z\xbc\xaf\x27\x1c': ('7z', 'application/7z'),
    b'\x1f\x8b': ('gzip', 'application/gzip'),

    # JSON可能以 { 或 [ 开头（文本格式）
    b'{': ('json', 'application/json'),
    b'[': ('json', 'application/json'),
}

class FileTypeDetector:
    """文件类型检测器（基于魔数签名）"""

    @staticmethod
    def detect_by_signature(file_path: Path) -> Optional[Tuple[str, str]]:
        """
        通过文件头魔数检测文件真实类型
        返回: (类型名, MIME类型) 或 None
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)  # 读取前32字节足够判断

            # 特殊处理：RIFF格式需要检查后续内容
            if header.startswith(b'RIFF'):
                # WebP: RIFF....WEBP
                if len(header) >= 12 and header[8:12] == b'WEBP':
                    return ('webp', 'image/webp')
                # AVI: RIFF....AVI
                if len(header) >= 12 and header[8:12] == b'AVI ':
                    return ('avi', 'video/avi')

            # 特殊处理：MP4有多种ftyp变体
            if len(header) >= 12 and b'ftyp' in header[:12]:
                return ('mp4', 'video/mp4')

            # 遍历签名表匹配
            for signature, (type_name, mime) in FILE_SIGNATURES.items():
                if header.startswith(signature):
                    return (type_name, mime)

            return None

        except Exception as e:
            logger.debug(f"魔数检测失败 {file_path}: {e}")
            return None

    @staticmethod
    def try_filetype_library(file_path: Path) -> Optional[Tuple[str, str]]:
        """
        使用 filetype 库检测（如果已安装）
        filetype 是纯Python库，支持50+种格式
        安装: pip install filetype
        """
        try:
            import filetype
            kind = filetype.guess(str(file_path))
            if kind is not None:
                return (kind.extension, kind.mime)
        except ImportError:
            logger.debug("filetype库未安装，跳过")
        except Exception as e:
            logger.debug(f"filetype检测失败: {e}")
        return None

    @staticmethod
    def detect_real_type(file_path: Path) -> Tuple[Optional[str], Optional[str]]:
        """
        综合检测文件真实类型
        优先使用 filetype 库（更准确），fallback到魔数检测
        返回: (类型名, MIME类型) 或 (None, None)
        """
        # 方法1：尝试 filetype 库
        result = FileTypeDetector.try_filetype_library(file_path)
        if result:
            return result

        # 方法2：魔数检测
        result = FileTypeDetector.detect_by_signature(file_path)
        if result:
            return result

        return (None, None)


# ==================== FFmpeg 检测 ====================

class FFmpegHelper:
    """FFmpeg/FFprobe 辅助类（用于视频元数据提取）"""

    _available = None  # 缓存检测结果

    @classmethod
    def is_available(cls) -> bool:
        """
        检测系统是否安装了 ffprobe
        """
        if cls._available is not None:
            return cls._available

        try:
            result = subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            cls._available = result.returncode == 0
            if cls._available:
                logger.info("✓ FFprobe 已安装，支持视频元数据提取")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cls._available = False
            logger.info("ℹ FFprobe 未安装，视频元数据提取功能受限")

        return cls._available

    @classmethod
    def extract_metadata(cls, file_path: Path) -> Optional[Dict]:
        """
        使用 ffprobe 提取视频文件的完整元数据
        返回: 元数据字典 或 None

        依赖: ffmpeg/ffprobe 需单独安装
        Windows下载: https://ffmpeg.org/download.html
        """
        if not cls.is_available():
            return None

        try:
            # 使用 ffprobe 提取所有元数据，输出为JSON格式
            cmd = [
                'ffprobe',
                '-v', 'quiet',  # 隐藏日志输出
                '-print_format', 'json',  # JSON格式输出
                '-show_format',  # 显示格式信息（包含tags）
                '-show_streams',  # 显示流信息
                str(file_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            if result.returncode != 0:
                return None

            # 使用 UTF-8 解码，避免 GBK 编码问题
            stdout_text = result.stdout.decode('utf-8', errors='ignore')
            metadata = json.loads(stdout_text)
            return metadata

        except subprocess.TimeoutExpired:
            logger.debug(f"ffprobe超时 {file_path}")
            return None
        except json.JSONDecodeError:
            logger.debug(f"ffprobe输出解析失败 {file_path}")
            return None
        except Exception as e:
            logger.debug(f"ffprobe执行失败 {file_path}: {e}")
            return None

    @classmethod
    def extract_workflow_from_video(cls, file_path: Path) -> Optional[Dict]:
        """
        从视频文件元数据中提取 ComfyUI 工作流

        ComfyUI 视频节点（如 SaveAnimatedWEBM）可能在元数据tags中存储工作流：
        - format.tags.comment
        - format.tags.description
        - format.tags.workflow
        """
        metadata = cls.extract_metadata(file_path)
        if metadata is None:
            return None

        # 检查 format.tags（容器级别的元数据）
        format_info = metadata.get('format', {})
        tags = format_info.get('tags', {})

        # 可能的键名
        possible_keys = ['workflow', 'prompt', 'comment', 'description', 'COMFYUI_WORKFLOW']

        for key in possible_keys:
            if key in tags:
                try:
                    value = tags[key]
                    if isinstance(value, str):
                        workflow_data = json.loads(value)
                        return workflow_data
                    elif isinstance(value, dict):
                        return value
                except json.JSONDecodeError:
                    continue

        # 检查视频流元数据
        streams = metadata.get('streams', [])
        for stream in streams:
            stream_tags = stream.get('tags', {})
            for key in possible_keys:
                if key in stream_tags:
                    try:
                        value = stream_tags[key]
                        if isinstance(value, str):
                            workflow_data = json.loads(value)
                            return workflow_data
                    except json.JSONDecodeError:
                        continue

        return None


# ==================== 核心类定义 ====================

class ComfyUIExtractor:
    """ComfyUI工作流提取器主类（增强版）"""

    def __init__(self, output_base: Path):
        self.output_base = output_base
        self.workflows_json_dir = output_base / WORKFLOW_JSON_DIR
        self.workflows_media_dir = output_base / WORKFLOW_MEDIA_DIR
        self.workflows_unknown_dir = output_base / WORKFLOW_UNKNOWN_DIR
        self.archives_dir = output_base / ARCHIVES_DIR
        self.history_file = output_base / HISTORY_FILE
        self.workflow_mapping_file = output_base / WORKFLOW_MAPPING_FILE

        # 扫描统计
        self.stats = {
            'total_scanned': 0,
            'json_workflows': 0,
            'media_workflows': 0,
            'unknown_workflows': 0,  # 新增：未知后缀的工作流
            'archives': 0,
            'skipped': 0,
            'errors': 0,
            'detected_by_signature': 0,  # 通过魔数检测识别的文件
        }

        # 已扫描文件记录（路径 → 哈希映射，确保对应关系正确）
        self.scanned_files: Dict[str, str] = {}  # 文件路径 -> SHA256哈希
        self.output_hashes: Set[str] = set()  # 输出目录中已有的哈希（去重用）

        # 工作流映射记录（记录每个文件对应的工作流信息）
        self.workflow_records: list = []

        # 处理计数器（用于定期保存）
        self.processed_count: int = 0

        # FFprobe可用性
        self.ffprobe_available = FFmpegHelper.is_available()

        # 注册信号处理（确保中断时保存进度）
        self._register_signal_handlers()

    def _register_signal_handlers(self):
        """注册信号处理器，确保中断时保存进度"""
        def handle_interrupt(signum, frame):
            logger.warning(f"收到中断信号 ({signum}), 正在保存进度...")
            self.save_history()
            self.save_workflow_mapping()
            logger.info("进度已保存，程序退出")
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_interrupt)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, handle_interrupt)

    def _check_and_save_periodically(self):
        """定期保存进度"""
        self.processed_count += 1
        if self.processed_count % SAVE_INTERVAL == 0:
            logger.info(f"已处理 {self.processed_count} 个文件，正在保存进度...")
            self.save_history()
            self.save_workflow_mapping()

    def setup_directories(self):
        """创建输出目录结构"""
        self.output_base.mkdir(parents=True, exist_ok=True)
        self.workflows_json_dir.mkdir(exist_ok=True)
        self.workflows_media_dir.mkdir(exist_ok=True)
        self.workflows_unknown_dir.mkdir(exist_ok=True)
        self.archives_dir.mkdir(exist_ok=True)
        logger.info(f"✓ 输出目录创建完成: {self.output_base}")

        # 清理已有的重复文件
        self.cleanup_duplicates()

    def cleanup_duplicates(self):
        """清理输出目录中已有的重复文件，并构建哈希集合"""
        logger.info("检查并清理重复文件...")

        hash_map = {}
        duplicates_found = 0

        for subdir in [self.workflows_json_dir, self.workflows_media_dir,
                       self.workflows_unknown_dir, self.archives_dir]:
            if not subdir.exists():
                continue

            for file_path in subdir.rglob('*'):
                if not file_path.is_file():
                    continue

                try:
                    file_hash = self.calculate_file_hash(file_path)
                    if file_hash:
                        if file_hash in hash_map:
                            # 发现重复，删除较新的文件
                            existing_file = hash_map[file_hash]
                            if file_path.stat().st_mtime > existing_file.stat().st_mtime:
                                # 当前文件较新，删除它
                                file_path.unlink()
                                duplicates_found += 1
                                logger.debug(f"删除重复文件: {file_path.name}")
                            else:
                                # 已有文件较新或相同时间，删除已有文件
                                existing_file.unlink()
                                duplicates_found += 1
                                logger.debug(f"删除重复文件: {existing_file.name}")
                                hash_map[file_hash] = file_path
                        else:
                            hash_map[file_hash] = file_path
                            # 添加到输出哈希集合
                            self.output_hashes.add(file_hash)
                except Exception as e:
                    logger.debug(f"处理文件失败: {file_path.name} - {e}")

        if duplicates_found > 0:
            logger.info(f"✓ 清理了 {duplicates_found} 个重复文件")
        else:
            logger.info("✓ 无重复文件需要清理")
        logger.info(f"✓ 输出目录已有 {len(self.output_hashes)} 个唯一文件哈希")

    def load_history(self):
        """加载扫描历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    # 支持新旧两种格式
                    if 'file_hashes' in history:
                        # 新格式：字典 {路径: 哈希}
                        self.scanned_files = history.get('file_hashes', {})
                    else:
                        # 旧格式：分离的files和hashes数组（合并为字典）
                        files = history.get('files', [])
                        hashes = history.get('hashes', [])
                        # 尽量匹配，如果数量不一致则只保存路径
                        if len(files) == len(hashes):
                            self.scanned_files = {f: h for f, h in zip(files, hashes)}
                        else:
                            self.scanned_files = {f: '' for f in files}
                logger.info(f"✓ 已加载历史记录: {len(self.scanned_files)} 个文件路径")
            except Exception as e:
                logger.warning(f"⚠ 加载历史记录失败，将从头开始: {e}")
                self.scanned_files = {}
        else:
            logger.info("ℹ 未找到历史记录文件，将从头开始扫描")

    def save_history(self):
        """保存扫描历史记录"""
        try:
            history = {
                'last_scan': datetime.now().isoformat(),
                'file_hashes': self.scanned_files,  # 新格式：字典 {路径: 哈希}
                'stats': self.stats
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ 历史记录已保存: {len(self.scanned_files)} 个文件路径")
        except Exception as e:
            logger.error(f"✗ 保存历史记录失败: {e}")

    def save_workflow_mapping(self):
        """保存工作流映射记录"""
        try:
            mapping = {
                'last_scan': datetime.now().isoformat(),
                'total_workflows': len(self.workflow_records),
                'records': self.workflow_records
            }
            with open(self.workflow_mapping_file, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ 工作流映射已保存: {len(self.workflow_records)} 条记录 → {self.workflow_mapping_file}")
        except Exception as e:
            logger.error(f"✗ 保存工作流映射失败: {e}")

    def calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """计算文件的SHA256哈希值（用于去重）"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.debug(f"计算哈希失败 {file_path}: {e}")
            return None

    def is_comfyui_workflow_json(self, data: Any) -> bool:
        """
        验证JSON数据是否为ComfyUI工作流结构
        核心特征：包含 "nodes" 和 "links" 键
        """
        if not isinstance(data, dict):
            return False

        # 检查标准工作流结构
        has_nodes = 'nodes' in data and isinstance(data['nodes'], list)
        has_links = 'links' in data and (isinstance(data['links'], list) or data['links'] is None)
        has_last_node_id = 'last_node_id' in data
        has_last_link_id = 'last_link_id' in data

        # ComfyUI工作流的典型特征
        if has_nodes and (has_links or has_last_node_id):
            return True

        # 额外检查：nodes数组中的元素结构
        if has_nodes and len(data['nodes']) > 0:
            first_node = data['nodes'][0]
            if isinstance(first_node, dict) and 'type' in first_node:
                return True

        return False

    def extract_workflow_summary(self, workflow: Dict) -> Dict:
        """
        从工作流数据中提取摘要信息
        返回包含节点数量、节点类型等关键信息
        """
        summary = {
            'node_count': 0,
            'link_count': 0,
            'node_types': [],
            'last_node_id': None,
            'last_link_id': None,
        }

        if not isinstance(workflow, dict):
            return summary

        # 获取节点数量
        nodes = workflow.get('nodes', [])
        summary['node_count'] = len(nodes)

        # 获取连接数量
        links = workflow.get('links', [])
        if links:
            summary['link_count'] = len(links)

        # 获取节点类型列表（去重）
        node_types = set()
        for node in nodes:
            if isinstance(node, dict) and 'type' in node:
                node_types.add(node['type'])
        summary['node_types'] = sorted(list(node_types))[:20]  # 最多显示20种类型

        # 其他信息
        summary['last_node_id'] = workflow.get('last_node_id')
        summary['last_link_id'] = workflow.get('last_link_id')

        return summary

    def extract_workflow_from_json_content(self, file_path: Path) -> Optional[Dict]:
        """
        尝试将文件内容作为JSON解析并提取工作流
        """
        try:
            # 检查文件大小，避免处理超大文件
            file_size = file_path.stat().st_size
            if file_size > MAX_FILE_SIZE_TO_PARSE:
                logger.debug(f"文件过大，跳过JSON解析: {file_path.name} ({file_size/1024/1024:.1f}MB)")
                return None

            # 尝试多种编码
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin1']
            content = None

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = json.load(f)
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

            if content is None:
                return None

            if self.is_comfyui_workflow_json(content):
                return content

            return None

        except Exception as e:
            logger.debug(f"JSON解析失败 {file_path}: {e}")
            return None

    def extract_workflow_from_image(self, file_path: Path) -> Optional[Dict]:
        """
        从图片文件提取ComfyUI工作流元数据

        根据联网搜索结果：
        - PNG: 工作流存储在tEXt/iTXt块中，键名为 "prompt"
        - WebP: 存储在EXIF元数据或RIFF块中
        - 其他格式：尝试读取元数据
        """
        try:
            with Image.open(file_path) as img:
                # 方法1：img.text字典（PNG文本块）
                if hasattr(img, 'text'):
                    # ComfyUI标准键：prompt
                    for key in ['prompt', 'workflow', 'Workflow', 'comfyui']:
                        if key in img.text:
                            try:
                                workflow_data = json.loads(img.text[key])
                                if self.is_comfyui_workflow_json(workflow_data):
                                    logger.debug(f"✓ 从PNG文本块[{key}]提取工作流: {file_path.name}")
                                    return workflow_data
                            except json.JSONDecodeError:
                                continue

                # 方法2：img.info字典（WebP等）
                if hasattr(img, 'info'):
                    for key in ['workflow', 'prompt', 'exif']:
                        if key in img.info:
                            try:
                                value = img.info[key]
                                if isinstance(value, str):
                                    workflow_data = json.loads(value)
                                    if self.is_comfyui_workflow_json(workflow_data):
                                        logger.debug(f"✓ 从图片info[{key}]提取工作流: {file_path.name}")
                                        return workflow_data
                                elif isinstance(value, dict):
                                    if self.is_comfyui_workflow_json(value):
                                        return value
                            except (json.JSONDecodeError, TypeError):
                                continue

            return None

        except Exception as e:
            logger.debug(f"图片元数据提取失败 {file_path}: {e}")
            return None

    def extract_workflow_from_video_ffprobe(self, file_path: Path) -> Optional[Dict]:
        """
        从视频文件提取ComfyUI工作流（使用ffprobe）
        """
        if not self.ffprobe_available:
            return None

        workflow = FFmpegHelper.extract_workflow_from_video(file_path)
        if workflow and self.is_comfyui_workflow_json(workflow):
            logger.debug(f"✓ 从视频元数据提取工作流: {file_path.name}")
            return workflow

        return None

    def scan_binary_for_workflow(self, file_path: Path) -> Optional[Dict]:
        """
        扫描二进制文件内容，查找嵌入的JSON工作流字符串
        适用于：改了后缀名的文件、未知格式文件

        搜索策略：查找可能的JSON工作流片段（以 "nodes" 开头的JSON）
        """
        try:
            # 限制扫描大小
            file_size = file_path.stat().st_size
            scan_size = min(file_size, MAX_FILE_SIZE_TO_PARSE)

            with open(file_path, 'rb') as f:
                content = f.read(scan_size)

            # 尝试查找包含 "nodes" 和 "links" 的JSON片段
            # 使用简单的字符串搜索，查找可能的JSON结构

            # 搜索特征字符串："nodes"
            nodes_marker = b'"nodes"'
            pos = content.find(nodes_marker)

            if pos == -1:
                return None

            # 尝试从找到的位置前后扩展，提取完整JSON
            # 回溯找到JSON起始位置（查找 '{' 或 '['）
            json_start = -1
            for i in range(max(0, pos - 1000), pos):
                if content[i:i+1] == b'{':
                    json_start = i
                    break

            if json_start == -1:
                return None

            # 尝试解析从起始位置开始的JSON
            # 由于难以确定结束位置，采用试探法：逐步扩展范围
            remaining = content[json_start:]

            # 尝试解析，每次扩展范围直到成功或超出限制
            max_attempts = 10
            chunk_size = 50000  # 每次尝试50KB

            for i in range(1, max_attempts + 1):
                try_chunk = remaining[:i * chunk_size]
                try:
                    # 尝试解码为文本并解析JSON
                    text = try_chunk.decode('utf-8', errors='ignore')

                    # 尝试找到有效的JSON边界
                    # 使用JSON解析器的容错性
                    try:
                        data = json.loads(text)
                        if self.is_comfyui_workflow_json(data):
                            logger.debug(f"✓ 二进制扫描发现工作流: {file_path.name}")
                            return data
                    except json.JSONDecodeError:
                        continue

                except Exception:
                    continue

            return None

        except Exception as e:
            logger.debug(f"二进制扫描失败 {file_path}: {e}")
            return None

    def try_all_extraction_methods(self, file_path: Path) -> Tuple[Optional[Dict], str]:
        """
        尝试所有可能的方法提取工作流
        返回: (工作流数据, 提取方法描述) 或 (None, "")

        方法顺序：
        1. JSON内容解析
        2. 图片元数据提取（Pillow）
        3. 视频元数据提取（FFprobe）
        4. 二进制扫描
        """
        # 方法1：作为JSON解析
        workflow = self.extract_workflow_from_json_content(file_path)
        if workflow:
            return (workflow, "JSON解析")

        # 方法2：作为图片提取元数据
        workflow = self.extract_workflow_from_image(file_path)
        if workflow:
            return (workflow, "图片元数据")

        # 方法3：作为视频提取元数据（需要ffprobe）
        workflow = self.extract_workflow_from_video_ffprobe(file_path)
        if workflow:
            return (workflow, "视频元数据(FFprobe)")

        # 方法4：二进制扫描查找嵌入JSON
        workflow = self.scan_binary_for_workflow(file_path)
        if workflow:
            return (workflow, "二进制扫描")

        return (None, "")

    def generate_unique_filename(self, target_dir: Path, original_name: str,
                                source_file: Path, detected_ext: Optional[str] = None) -> str:
        """
        生成唯一文件名，避免同名冲突
        detected_ext: 如果检测到真实文件类型，可以修正扩展名
        """
        # 如果需要修正扩展名
        if detected_ext:
            stem = Path(original_name).stem
            base_name = f"{stem}.{detected_ext}"
        else:
            base_name = original_name

        if (target_dir / base_name).exists():
            try:
                mtime = datetime.fromtimestamp(source_file.stat().st_mtime)
                timestamp = mtime.strftime("%Y%m%d_%H%M%S")
                stem = Path(base_name).stem
                ext = Path(base_name).suffix
                base_name = f"{stem}_{timestamp}{ext}"
            except:
                stem = Path(base_name).stem
                ext = Path(base_name).suffix
                short_uuid = str(uuid.uuid4())[:8]
                base_name = f"{stem}_{short_uuid}{ext}"

            counter = 0
            while (target_dir / base_name).exists():
                stem = Path(original_name).stem
                ext = Path(base_name).suffix
                short_uuid = str(uuid.uuid4())[:8]
                base_name = f"{stem}_{short_uuid}_{counter}{ext}"
                counter += 1

        return base_name

    def copy_file_with_dedup(self, source: Path, target_dir: Path, category: str,
                            detected_ext: Optional[str] = None) -> bool:
        """
        复制文件到目标目录，保留时间戳，处理同名冲突
        检查历史记录和输出目录哈希，防止重复复制
        """
        try:
            file_hash = self.calculate_file_hash(source)
            # 检查哈希是否已存在（历史记录或输出目录）
            if file_hash:
                if file_hash in self.scanned_files.values():
                    logger.debug(f"跳过重复文件（历史哈希匹配）: {source.name}")
                    self.stats['skipped'] += 1
                    return False
                if file_hash in self.output_hashes:
                    logger.debug(f"跳过重复文件（输出目录哈希匹配）: {source.name}")
                    self.stats['skipped'] += 1
                    return False

            target_filename = self.generate_unique_filename(target_dir, source.name, source, detected_ext)
            target_path = target_dir / target_filename

            shutil.copy2(source, target_path)

            # 添加到字典：路径 → 哈希
            self.scanned_files[str(source.resolve())] = file_hash or ''
            # 同时添加到输出哈希集合
            if file_hash:
                self.output_hashes.add(file_hash)

            logger.info(f"  ✓ 复制成功 [{category}]: {source.name} → {target_filename}")
            return True

        except PermissionError as e:
            logger.warning(f"⚠ 权限不足，跳过文件: {source} - {e}")
            self.stats['errors'] += 1
            return False
        except OSError as e:
            logger.warning(f"⚠ 系统错误，跳过文件: {source} - {e}")
            self.stats['errors'] += 1
            return False
        except Exception as e:
            logger.error(f"✗ 复制失败: {source} - {e}")
            self.stats['errors'] += 1
            return False

    def copy_related_media_files(self, json_file: Path):
        """
        当发现JSON工作流时，复制同目录下的所有媒体资源文件
        包括：PNG、WebP、MP4、WebM等所有媒体格式
        """
        source_dir = json_file.parent
        json_name = json_file.stem  # 工作流名称（不含扩展名）
        media_count = 0

        # 搜索同目录下的所有媒体文件
        for media_file in source_dir.iterdir():
            if not media_file.is_file():
                continue
            if media_file == json_file:
                continue

            media_ext = media_file.suffix.lower()
            # 只处理媒体文件（图片、视频）
            if media_ext not in MEDIA_EXTENSIONS:
                continue

            # 检查是否已处理
            media_path_str = str(media_file.resolve())
            if media_path_str in self.scanned_files:
                continue

            # 复制媒体文件
            if self.copy_file_with_dedup(media_file, self.workflows_media_dir, '关联媒体', None):
                media_count += 1
                self.stats['media_workflows'] += 1

                # ★ 创建映射记录：媒体文件 → 关联的工作流JSON
                record = {
                    'source_path': media_path_str,
                    'target_filename': media_file.name,
                    'target_dir': 'Workflows_Media',
                    'category': '关联媒体',
                    'extraction_method': '关联复制',
                    'file_extension': media_ext,
                    'detected_type': None,
                    'workflow_summary': {'node_count': 0, 'link_count': 0, 'node_types': []},
                    'scan_time': datetime.now().isoformat(),
                    'related_workflow': str(json_file.resolve()),  # 关联的JSON工作流路径
                    'related_workflow_name': json_file.name,  # 关联的JSON工作流文件名
                }
                self.workflow_records.append(record)

        if media_count > 0:
            logger.info(f"  ✓ 关联复制 {media_count} 个媒体文件 → {json_file.name}")

    def process_file(self, file_path: Path):
        """
        处理单个文件（增强版）：无视后缀名，尝试所有提取方法
        """
        self.stats['total_scanned'] += 1
        self._check_and_save_periodically()  # 定期保存进度

        # 检查是否已扫描
        file_path_str = str(file_path.resolve())
        if file_path_str in self.scanned_files:
            logger.debug(f"跳过已扫描文件: {file_path.name}")
            self.stats['skipped'] += 1
            return

        # 获取文件扩展名
        ext = file_path.suffix.lower()
        has_known_ext = ext in (JSON_EXTENSION, MEDIA_EXTENSIONS, ARCHIVE_EXTENSIONS)

        # 检测文件真实类型（通过魔数）
        detected_type, detected_mime = FileTypeDetector.detect_real_type(file_path)

        try:
            # ===== 压缩包处理 =====
            # 如果扩展名是压缩包，或者检测出是压缩包
            is_archive = ext in ARCHIVE_EXTENSIONS or detected_type in ('zip', 'rar', '7z', 'gzip', 'tar')
            if is_archive:
                if self.copy_file_with_dedup(file_path, self.archives_dir, '压缩包', detected_type):
                    self.stats['archives'] += 1
                return

            # ===== 工作流提取 =====
            # 对所有文件尝试提取工作流（包括未知后缀）
            workflow, method = self.try_all_extraction_methods(file_path)

            if workflow:
                # 确定目标目录和类别
                if ext == JSON_EXTENSION:
                    target_dir = self.workflows_json_dir
                    category = 'JSON工作流'
                elif ext in MEDIA_EXTENSIONS:
                    target_dir = self.workflows_media_dir
                    category = f'媒体工作流({method})'
                    self.stats['media_workflows'] += 1
                else:
                    # 未知后缀名的工作流！
                    target_dir = self.workflows_unknown_dir
                    category = f'未知后缀({method})'
                    self.stats['unknown_workflows'] += 1
                    self.stats['detected_by_signature'] += 1
                    logger.info(f"✓ 发现隐藏工作流！后缀={ext} 真实类型={detected_type} 方法={method}: {file_path.name}")

                # 生成目标文件名并复制
                target_filename = self.generate_unique_filename(target_dir, file_path.name, file_path, detected_type)
                target_path = target_dir / target_filename

                # ★ JSON工作流：无论是否重复，都要复制同目录媒体文件
                if ext == JSON_EXTENSION:
                    self.copy_related_media_files(file_path)

                # 复制JSON文件本身（可能因重复而跳过）
                if self.copy_file_with_dedup(file_path, target_dir, category, detected_type):
                    self.stats['json_workflows'] += 1  # 只有实际复制才计数
                    # 记录工作流映射信息
                    workflow_info = self.extract_workflow_summary(workflow)
                    record = {
                        'source_path': file_path_str,
                        'target_filename': target_filename,
                        'target_dir': target_dir.name,
                        'category': category,
                        'extraction_method': method,
                        'file_extension': ext,
                        'detected_type': detected_type,
                        'workflow_summary': workflow_info,
                        'scan_time': datetime.now().isoformat(),
                    }
                    self.workflow_records.append(record)

                return

            # ===== 对于未知后缀的文件，也尝试作为压缩包 =====
            if not has_known_ext and detected_type in ('zip', 'rar', '7z', 'gzip'):
                if self.copy_file_with_dedup(file_path, self.archives_dir, '压缩包(隐藏)', detected_type):
                    self.stats['archives'] += 1
                    self.stats['detected_by_signature'] += 1
                    logger.info(f"✓ 发现隐藏压缩包！后缀={ext} 真实类型={detected_type}: {file_path.name}")
                return

        except Exception as e:
            logger.error(f"✗ 处理文件失败 {file_path}: {e}")
            self.stats['errors'] += 1

    def scan_directory(self, dir_path: Path):
        """递归扫描目录"""
        try:
            logger.info(f"正在扫描目录: {dir_path}")

            for file_path in dir_path.rglob('*'):
                if not file_path.is_file():
                    continue

                try:
                    self.process_file(file_path)
                except Exception as e:
                    logger.debug(f"处理文件异常: {file_path} - {e}")
                    continue

        except PermissionError as e:
            logger.warning(f"⚠ 权限不足，跳过目录: {dir_path} - {e}")
        except OSError as e:
            logger.warning(f"⚠ 系统错误，跳过目录: {dir_path} - {e}")
        except Exception as e:
            logger.error(f"✗ 扫描目录失败: {dir_path} - {e}")

    def run(self):
        """主运行流程"""
        logger.info("=" * 70)
        logger.info("ComfyUI 工作流提取工具（增强版）启动")
        logger.info("支持：JSON、图片、视频、未知后缀文件")
        logger.info("=" * 70)

        self.setup_directories()
        self.load_history()

        for scan_path in SCAN_PATHS:
            path = Path(scan_path)
            if not path.exists():
                logger.warning(f"⚠ 路径不存在，跳过: {path}")
                continue
            if not path.is_dir():
                logger.warning(f"⚠ 不是目录，跳过: {path}")
                continue
            self.scan_directory(path)

        self.save_history()
        self.save_workflow_mapping()
        self.print_summary()

    def print_summary(self):
        """打印扫描统计摘要"""
        logger.info("=" * 70)
        logger.info("扫描完成！统计摘要：")
        logger.info(f"  总扫描文件数: {self.stats['total_scanned']}")
        logger.info(f"  JSON工作流文件: {self.stats['json_workflows']}")
        logger.info(f"  媒体工作流文件: {self.stats['media_workflows']}")
        logger.info(f"  未知后缀工作流: {self.stats['unknown_workflows']} ⭐")
        logger.info(f"  压缩包文件: {self.stats['archives']}")
        logger.info(f"  跳过文件数: {self.stats['skipped']}")
        logger.info(f"  错误文件数: {self.stats['errors']}")
        logger.info(f"  魔数检测识别: {self.stats['detected_by_signature']}")
        logger.info("=" * 70)
        logger.info(f"输出目录: {self.output_base}")
        logger.info(f"  - JSON工作流: {self.workflows_json_dir}")
        logger.info(f"  - 媒体工作流: {self.workflows_media_dir}")
        logger.info(f"  - 未知后缀工作流: {self.workflows_unknown_dir} ⭐")
        logger.info(f"  - 压缩包: {self.archives_dir}")
        logger.info("=" * 70)


def identify_workflow(file_path: str) -> Optional[Dict]:
    """
    从指定文件中识别并提取 ComfyUI 工作流信息

    Args:
        file_path: 文件路径（可以是图片、视频、JSON等）

    Returns:
        工作流数据字典，如果提取失败返回 None
    """
    path = Path(file_path)
    if not path.exists():
        logger.error(f"文件不存在: {file_path}")
        return None

    # 创建临时提取器实例
    output_base = Path.cwd() / OUTPUT_DIR_NAME
    extractor = ComfyUIExtractor(output_base)

    # 尝试所有提取方法
    workflow, method = extractor.try_all_extraction_methods(path)

    if workflow:
        summary = extractor.extract_workflow_summary(workflow)
        logger.info("=" * 50)
        logger.info(f"文件: {path.name}")
        logger.info(f"提取方法: {method}")
        logger.info(f"节点数量: {summary['node_count']}")
        logger.info(f"连接数量: {summary['link_count']}")
        logger.info(f"节点类型: {', '.join(summary['node_types'][:10])}")
        if len(summary['node_types']) > 10:
            logger.info(f"  ... 还有 {len(summary['node_types']) - 10} 种类型")
        logger.info("=" * 50)
        return workflow
    else:
        logger.warning(f"未检测到 ComfyUI 工作流: {file_path}")
        return None


def query_workflow_mapping(mapping_file: str = None, filename: str = None) -> Optional[Dict]:
    """
    查询工作流映射记录，找到指定文件的工作流信息

    Args:
        mapping_file: 映射文件路径（默认为输出目录下的 workflow_mapping.json）
        filename: 要查询的文件名

    Returns:
        匹配的记录，如果没有找到返回 None
    """
    if mapping_file is None:
        mapping_file = Path.cwd() / OUTPUT_DIR_NAME / WORKFLOW_MAPPING_FILE

    path = Path(mapping_file)
    if not path.exists():
        logger.error(f"映射文件不存在: {mapping_file}")
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            mapping = json.load(f)

        records = mapping.get('records', [])

        if filename:
            # 查找匹配的记录
            matches = [r for r in records if r.get('target_filename') == filename or r.get('source_path', '').endswith(filename)]
            if matches:
                for match in matches:
                    logger.info("=" * 50)
                    logger.info(f"源文件: {match['source_path']}")
                    logger.info(f"目标文件: {match['target_filename']}")
                    logger.info(f"目录: {match['target_dir']}")
                    logger.info(f"提取方法: {match['extraction_method']}")
                    logger.info(f"节点数量: {match['workflow_summary']['node_count']}")
                    logger.info(f"节点类型: {', '.join(match['workflow_summary']['node_types'][:10])}")
                    logger.info("=" * 50)
                return matches[0]
            else:
                logger.warning(f"未找到文件 {filename} 的记录")
                return None
        else:
            # 显示所有记录摘要
            logger.info(f"总共有 {len(records)} 条工作流记录")
            for r in records[:20]:  # 只显示前20条
                logger.info(f"  {r['target_filename']} -> {r['workflow_summary']['node_count']} 节点 ({r['extraction_method']})")
            if len(records) > 20:
                logger.info(f"  ... 还有 {len(records) - 20} 条记录")
            return mapping
    except Exception as e:
        logger.error(f"读取映射文件失败: {e}")
        return None


# ==================== 主程序入口 ====================

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='ComfyUI 工作流提取工具')
    parser.add_argument('action', nargs='?', default='scan',
                        help='操作类型: scan(扫描), identify(识别文件), query(查询映射)')
    parser.add_argument('--file', '-f', type=str,
                        help='要识别的文件路径（用于 identify 操作）')
    parser.add_argument('--name', '-n', type=str,
                        help='要查询的文件名（用于 query 操作）')
    parser.add_argument('--output', '-o', type=str,
                        help='自定义输出目录名称（不带路径，仅目录名）')
    parser.add_argument('--incremental', '-i', type=str,
                        help='增量扫描：指定旧输出目录路径，加载其历史记录只扫描新文件')
    parser.add_argument('--date-output', '-d', action='store_true',
                        help='输出目录名添加日期后缀（格式：_YYYYMMDD）')

    args = parser.parse_args()

    # 确定输出目录
    base_output_name = args.output if args.output else OUTPUT_DIR_NAME
    if args.date_output:
        date_suffix = datetime.now().strftime('_%Y%m%d')
        base_output_name = base_output_name + date_suffix
    output_base = Path.cwd() / base_output_name

    if args.action == 'identify':
        # 识别指定文件的工作流
        if not args.file:
            logger.error("请指定要识别的文件: --file <路径>")
            return
        identify_workflow(args.file)

    elif args.action == 'query':
        # 查询工作流映射
        query_workflow_mapping(filename=args.name)

    else:
        # 默认：扫描模式
        extractor = ComfyUIExtractor(output_base)

        # 增量扫描：从旧输出目录的实际文件计算哈希（不依赖可能错误的历史文件）
        if args.incremental:
            old_output_path = Path(args.incremental)
            if not old_output_path.exists():
                old_output_path = Path.cwd() / args.incremental

            if old_output_path.exists() and old_output_path.is_dir():
                # 直接从旧输出目录的文件计算正确哈希（可靠方式）
                logger.info(f"✓ 增量模式：从 {old_output_path} 目录计算文件哈希...")
                hash_count = 0
                for subdir in [old_output_path / WORKFLOW_JSON_DIR,
                               old_output_path / WORKFLOW_MEDIA_DIR,
                               old_output_path / WORKFLOW_UNKNOWN_DIR,
                               old_output_path / ARCHIVES_DIR]:
                    if not subdir.exists():
                        continue
                    for file_path in subdir.rglob('*'):
                        if not file_path.is_file():
                            continue
                        try:
                            sha256_hash = hashlib.sha256()
                            with open(file_path, 'rb') as f:
                                for byte_block in iter(lambda: f.read(65536), b''):
                                    sha256_hash.update(byte_block)
                            file_hash = sha256_hash.hexdigest()
                            if file_hash:
                                extractor.output_hashes.add(file_hash)
                                hash_count += 1
                        except Exception:
                            continue
                logger.info(f"  已加载哈希: {hash_count} 个（从实际文件计算，用于内容去重）")

        try:
            extractor.run()
        except KeyboardInterrupt:
            logger.info("\n用户中断，正在保存进度...")
            extractor.save_history()
            extractor.save_workflow_mapping()
            logger.info("进度已保存，程序退出")
        except Exception as e:
            logger.error(f"程序异常终止: {e}", exc_info=True)
            extractor.save_history()
            extractor.save_workflow_mapping()
            raise


if __name__ == "__main__":
    main()