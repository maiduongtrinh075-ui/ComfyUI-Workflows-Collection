#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一的路径与配置中心。

设计目标：
1. 项目根目录 = 本文件所在目录，所有"项目内"产物默认放在项目根下，避免硬编码绝对路径。
2. "用户机器路径"（ComfyUI 模型目录、扫描的微信/QQ 缓存目录等）通过环境变量
   或 user_config.json 覆盖，不再写死 F:/... 或 C:/Users/Swioon/...
3. 其它脚本通过 `from paths import ...` 取路径。

优先级：环境变量 > user_config.json > 内置默认值。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

PROJECT_ROOT: Path = Path(__file__).resolve().parent
USER_CONFIG_FILE: Path = PROJECT_ROOT / "user_config.json"


def _load_user_config() -> dict:
    if USER_CONFIG_FILE.exists():
        try:
            with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}
    return {}


_USER_CONFIG = _load_user_config()


def _resolve(env_key: str, config_key: str, default):
    """环境变量 > user_config.json > 默认值。"""
    raw = os.environ.get(env_key)
    if raw is None:
        raw = _USER_CONFIG.get(config_key)
    if raw is None:
        return default
    if isinstance(default, list):
        if isinstance(raw, list):
            return raw
        return [p for p in str(raw).split(os.pathsep) if p]
    if isinstance(default, Path):
        return Path(raw)
    return raw


# ---- 输出根 ---------------------------------------------------------------
OUTPUT_DIR_NAME = "Extracted_ComfyUI_Assets"
OUTPUT_DIR: Path = _resolve("OUTPUT_DIR", "output_dir", PROJECT_ROOT / OUTPUT_DIR_NAME)

WORKFLOWS_JSON_DIR: Path = OUTPUT_DIR / "Workflows_JSON"
WORKFLOWS_MEDIA_DIR: Path = OUTPUT_DIR / "Workflows_Media"
WORKFLOWS_UNKNOWN_DIR: Path = OUTPUT_DIR / "Workflows_Unknown"
WORKFLOWS_JSON_FROM_MEDIA_DIR: Path = OUTPUT_DIR / "Workflows_JSON_From_Media"
ARCHIVES_DIR: Path = OUTPUT_DIR / "Archives"

HISTORY_FILE: Path = OUTPUT_DIR / "scanned_history.json"
WORKFLOW_MAPPING_FILE: Path = OUTPUT_DIR / "workflow_mapping.json"
MEDIA_WORKFLOW_MAPPING_FILE: Path = OUTPUT_DIR / "media_workflow_mapping.json"
DB_FILE: Path = OUTPUT_DIR / "comfyui_workflows.db"

MODEL_RESOURCES_CSV: Path = OUTPUT_DIR / "model_resources.csv"
MODEL_RESOURCES_CSV_LEGACY: Path = PROJECT_ROOT / "model_resources.csv"

MISSING_MODELS_CSV: Path = OUTPUT_DIR / "missing_models.csv"
MISSING_MODELS_REPORT_HTML: Path = OUTPUT_DIR / "missing_models_report.html"
WORKFLOW_STATS_REPORT_HTML: Path = OUTPUT_DIR / "workflow_stats_report.html"

# ---- ComfyUI 模型目录 -----------------------------------------------------
COMFYUI_MODELS_DIR: Path = _resolve(
    "COMFYUI_MODELS_DIR",
    "comfyui_models_dir",
    PROJECT_ROOT.parent / "ComfyUI" / "models",
)

MODEL_DIR_MAP = {
    "checkpoint": "checkpoints",
    "lora": "loras",
    "vae": "vae",
    "clip": "clip",
    "controlnet": "controlnet",
    "upscale_model": "upscale_models",
    "unet": "unet",
    "embedding": "embeddings",
    "style_model": "style_models",
}

# ---- 代理 / FFprobe / GUI 文件 -------------------------------------------
PROXY: str = _resolve("PROXY", "proxy", "http://127.0.0.1:7890")
FFPROBE_PATH: str = _resolve("FFPROBE_PATH", "ffprobe_path", "ffprobe")

GUI_CONFIG_FILE: Path = PROJECT_ROOT / "gui_config.json"
GUI_ICON_FILE: Path = PROJECT_ROOT / "icon.ico"


# ---- 扫描路径默认值 -------------------------------------------------------
def _default_scan_paths() -> List[str]:
    user_profile = os.environ.get("USERPROFILE") or str(Path.home())
    base = Path(user_profile)
    candidates = [
        base / "xwechat_files",
        base / "Documents" / "Tencent Files",
        base / "Documents" / "WeChat Files",
        base / "Downloads",
    ]
    return [str(p) for p in candidates if p.exists()]


_user_scan_paths = _USER_CONFIG.get("scan_paths")
if isinstance(_user_scan_paths, list) and _user_scan_paths:
    SCAN_PATHS: List[str] = list(_user_scan_paths)
else:
    SCAN_PATHS = _default_scan_paths()


def ensure_output_dirs() -> None:
    """确保所有输出子目录存在。"""
    for d in (
        OUTPUT_DIR,
        WORKFLOWS_JSON_DIR,
        WORKFLOWS_MEDIA_DIR,
        WORKFLOWS_UNKNOWN_DIR,
        WORKFLOWS_JSON_FROM_MEDIA_DIR,
        ARCHIVES_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


__all__ = [
    "PROJECT_ROOT", "USER_CONFIG_FILE",
    "OUTPUT_DIR_NAME", "OUTPUT_DIR",
    "WORKFLOWS_JSON_DIR", "WORKFLOWS_MEDIA_DIR", "WORKFLOWS_UNKNOWN_DIR",
    "WORKFLOWS_JSON_FROM_MEDIA_DIR", "ARCHIVES_DIR",
    "HISTORY_FILE", "WORKFLOW_MAPPING_FILE", "MEDIA_WORKFLOW_MAPPING_FILE",
    "DB_FILE", "MODEL_RESOURCES_CSV", "MODEL_RESOURCES_CSV_LEGACY",
    "MISSING_MODELS_CSV", "MISSING_MODELS_REPORT_HTML", "WORKFLOW_STATS_REPORT_HTML",
    "COMFYUI_MODELS_DIR", "MODEL_DIR_MAP",
    "PROXY", "FFPROBE_PATH",
    "GUI_CONFIG_FILE", "GUI_ICON_FILE",
    "SCAN_PATHS", "ensure_output_dirs",
]
