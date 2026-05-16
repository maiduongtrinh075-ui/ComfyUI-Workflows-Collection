# ComfyUI 工作流提取工具（增强版）

自动扫描微信/腾讯软件缓存目录，提取 ComfyUI 工作流文件和压缩包。
**增强版支持视频文件、未知后缀名文件、文件魔数检测！**

## ✨ 功能特性

### 1. 智能特征识别（无视后缀名）
- **JSON文件**：验证 ComfyUI 工作流结构（`nodes` + `links`）
- **图片文件**：PNG/WebP/GIF 等提取嵌入的工作流元数据
- **视频文件**：MP4/WebM/MKV 等提取元数据中的工作流（需FFprobe）
- **未知后缀文件**：通过文件魔数检测真实类型，尝试所有解析方法

### 2. 文件魔数检测
即使文件被改名混淆后缀，也能识别真实类型：
- PNG → `\x89PNG\r\n\x1a\n`
- JPEG → `\xff\xd8\xff`
- MP4 → `ftyp` 标记
- ZIP → `PK\x03\x04`
- 等等...

### 3. 多重解析策略
对每个文件依次尝试：
1. JSON 内容解析
2. 图片元数据提取（Pillow）
3. 视频元数据提取（FFprobe）
4. 二进制扫描查找嵌入 JSON

### 4. 增量扫描与内容去重
- **SHA256 哈希内容去重**：相同内容的文件只保留一份
- **智能增量模式**：从旧输出目录加载哈希，只提取新内容
- **支持中断恢复**：Ctrl+C 中断后下次继续扫描

### 5. 关联媒体文件复制
- **发现JSON工作流 → 自动复制同目录媒体文件**
- **映射记录**：每个媒体文件关联到对应的工作流JSON
- **便于查找**：通过 `workflow_mapping.json` 查询媒体文件对应哪个工作流

### 6. 完善异常处理
- 自动跳过无权限目录/文件
- 处理路径过长问题
- 容错损坏文件

## 📦 依赖安装

```bash
# 核心依赖（必需）
pip install Pillow

# 文件类型检测（可选，推荐）
pip install filetype

# 视频元数据提取（可选）
# FFprobe 需单独安装
# Windows: 下载 https://ffmpeg.org/download.html 并添加到PATH
```

或一键安装：

```bash
pip install -r requirements.txt
```

## 🚀 使用方法

```bash
python comfyui_extractor.py
```

## 📁 输出目录结构

```
Extracted_ComfyUI_Assets/
├── Workflows_JSON/       # 纯 JSON 工作流文件
├── Workflows_Media/      # 图片/视频工作流文件
├── Workflows_Unknown/    # ⭐ 未知后缀的工作流（隐藏文件）
├── Archives/             # 压缩包文件
└── scanned_history.json  # 扫描历史记录
```

## 🔧 技术要点

### ComfyUI 工作流元数据存储

| 文件类型 | 存储位置 | 键名 |
|---------|---------|-----|
| PNG | tEXt/iTXt 文本块 | `prompt` 或 `workflow` |
| WebP | EXIF 元数据 / RIFF块 | `workflow` |
| MP4/WebM | 容器元数据 tags | `workflow` 或 `comment` |

### 文件魔数签名表

```
PNG:     89 50 4E 47 0D 0A 1A 0A
JPEG:    FF D8 FF
GIF:     47 49 46 38 (GIF8)
WebP:    52 49 46 46 ... 57 45 42 50 (RIFF...WEBP)
MP4:     ... 66 74 79 70 ... (ftyp)
ZIP:     50 4B 03 04 (PK..)
```

### 同名冲突处理

- 使用源文件最后修改时间戳重命名
- 如仍冲突，追加短 UUID

## 📊 统计输出示例

```
======================================================================
扫描完成！统计摘要：
  总扫描文件数: 12543
  JSON工作流文件: 23
  媒体工作流文件: 156
  未知后缀工作流: 8 ⭐          ← 发现隐藏的工作流！
  压缩包文件: 45
  跳过文件数: 12300
  错误文件数: 11
  魔数检测识别: 12              ← 通过魔数识别的文件
======================================================================
```

## ⚙️ 配置修改

编辑脚本开头的配置区域：

```python
# 修改扫描路径
SCAN_PATHS = [
    r"C:\Users\YourName\xwechat_files",
    r"C:\Users\YourName\Documents\WeChat Files",
]

# 修改最大解析文件大小（默认100MB）
MAX_FILE_SIZE_TO_PARSE = 100 * 1024 * 1024
```

## 📝 使用场景

### 场景1：正常文件
```
workflow.json → Workflows_JSON/
output.png    → Workflows_Media/  (PNG含工作流)
video.webm    → Workflows_Media/  (视频含工作流)
project.zip   → Archives/
```

### 场景2：隐藏/混淆文件
```
image.dat     → Workflows_Unknown/  (魔数检测为PNG，含工作流)
workflow.txt  → Workflows_Unknown/  (实际是JSON)
video.bin     → Workflows_Unknown/  (魔数检测为MP4)
archive.dat   → Archives/           (魔数检测为ZIP)
```

## ⚠️ 注意事项

1. **权限要求**：需要读取微信/腾讯缓存目录，可能需要管理员权限
2. **首次运行**：扫描时间较长（取决于缓存文件数量）
3. **FFprobe**：视频元数据提取需要安装 FFmpeg
4. **大文件**：超过100MB的文件跳过深度解析（可配置）
5. **中断恢复**：Ctrl+C 中断后，下次继续扫描

## ⬇️ 模型下载功能

自动从Civitai下载缺失的模型文件：

### 使用方法

```bash
# 测试下载一个模型
python model_downloader.py --test

# 下载指定模型
python model_downloader.py --model "juggernaut" --type "checkpoint"

# 批量下载缺失模型（默认5个）
python model_downloader.py --batch 10
```

### GUI下载

在桌面工具中点击"⬇️ 下载缺失模型"按钮，自动下载前5个缺失模型。

### 功能特性

| 特性 | 说明 |
|-----|------|
| Civitai搜索 | 自动搜索模型并获取下载链接 |
| 进度显示 | 实时显示下载进度和速度 |
| 断点续传 | 支持中断后继续下载 |
| 自动分类 | 按模型类型放到对应目录 |

### 模型存放目录

下载的模型自动放到ComfyUI对应目录：

```
ComfyUI/models/
├── checkpoints/    ← checkpoint模型
├── loras/          ← LoRA模型
├── vae/            ← VAE模型
├── clip/           ← CLIP模型
├── controlnet/     ← ControlNet模型
└── upscale_models/ ← 放大模型
```

### 代理配置

下载需要访问Civitai，请确保代理配置正确：

```python
PROXY = "http://127.0.0.1:7890"  # 修改为你的代理地址
```

## 🎯 工作流模型下载

针对单个工作流，下载其所需的所有缺失模型：

### 使用方法

```bash
# 列出工作流引用的模型（不下载）
python workflow_model_downloader.py workflow.json --list

# 下载工作流缺失的所有模型
python workflow_model_downloader.py workflow.json

# 指定模型目录和代理
python workflow_model_downloader.py workflow.json --models-dir "F:/ComfyUI/models" --proxy "http://127.0.0.1:7890"

# 交互式选择工作流
python workflow_model_downloader.py
```

### 功能流程

```
1. 解析工作流JSON → 提取所有模型引用
2. 扫描本地ComfyUI → 检测已有模型
3. 对比生成缺失列表 → 显示缺失模型
4. 自动搜索Civitai → 下载缺失模型
```

### 输出示例

```
工作流: flux_workflow.json

工作流引用模型: 5 个
  checkpoint: 1 个 (flux-2-klein-9b-fp8.safetensors)
  vae: 1 个 (flux2-vae.safetensors)
  clip: 3 个 (flux2, default, qwen_3_8b_fp8mixed.safetensors)

缺失模型: 5 个
已有模型: 0 个

开始下载缺失模型...
```

## 🔧 模型资源提取

扫描工作流后，可提取所需的模型资源列表并获取下载链接：

```bash
python extract_model_resources.py
```

### 输出文件

`model_resources.csv` - 包含以下字段：

| 字段 | 说明 |
|------|------|
| type | 模型类型 (checkpoint/lora/vae/clip等) |
| name | 模型名称 |
| usage_count | 在工作流中的使用次数 |
| download_url | Civitai API下载链接 |
| page_url | Civitai 页面链接 |

### 支持的模型类型

- **checkpoint** - 主模型/底模
- **lora** - LoRA 微调模型
- **vae** - VAE 变分自编码器
- **clip** - CLIP 文本编码器
- **controlnet** - ControlNet 控制网络
- **upscale_model** - 放大模型
- **unet** - UNET 模型

### 统计示例

```
找到 731 个唯一模型：
  lora: 329 个
  unet: 169 个
  vae: 82 个
  checkpoint: 62 个
  clip: 51 个
  upscale_model: 20 个
  controlnet: 18 个

找到下载链接: 709 个 (97%)
```

## 📸 媒体工作流提取

从已提取的图片/视频文件中导出工作流JSON，方便一一对应查找：

```bash
python extract_media_workflows.py
```

### 功能特性

- 从 PNG 图片提取嵌入的工作流（tEXt/iTXt 元数据）
- 从 MP4/WebM 视频提取工作流（FFprobe 元数据）
- **SHA256 哈希去重**：相同工作流只保存一份JSON
- 生成映射表，记录媒体文件与JSON的一一对应关系

### 输出目录结构

```
Extracted_ComfyUI_Assets/
├── Workflows_Media/           # 原始媒体文件 (344个)
├── Workflows_JSON_From_Media/ # 提取的工作流JSON (87个唯一)
└── media_workflow_mapping.json # 媒体与JSON对应关系
```

### 映射表格式

```json
{
  "mappings": [
    {
      "media_file": "xxx.mp4",
      "workflow_json": "xxx_workflow.json",
      "workflow_hash": "abc123",
      "is_duplicate": false
    }
  ]
}
```

- `is_duplicate: false` → 有自己的唯一JSON文件
- `is_duplicate: true` → 指向已有的JSON（重复工作流）

### 统计示例

```
媒体文件总数: 344 个 (255 图片 + 89 视频)
唯一工作流: 87 个
重复工作流: 257 个
```

## 🔗 参考资料

- [Extracting ComfyUI Workflows from PNG Files](https://brendan.sanitylabs.com/extracting-comfyui-workflows-from-png-files)
- [Reddit: How to extract workflow data from ComfyUI](https://www.reddit.com/r/StableDiffusion/comments/1axdhqk/how_to_extract_workflow_data_from_comfyui/)
- [python-magic / filetype 库文档](https://github.com/h2non/filetype)
- [FFmpeg FFprobe 文档](https://ffmpeg.org/ffprobe.html)
- [Civitai API 文档](https://civitai.com/api/v1/models)

## 💬 QQ聊天记录导出 (QCE)

整合了 NapCat + QQ Chat Exporter (QCE) 工具，可以正规导出 QQ 聊天记录。

### 启动 QCE

```bash
# 方式1: 简单启动脚本
python start_qce.py

# 方式2: 统一CLI工具
python comfyui_tool.py --qce
```

启动后：
1. 等待 QQ 自动启动并登录
2. 浏览器访问 `http://localhost:6099/qce-v4-tool`
3. 在 Web UI 中导出聊天记录

### 交互式导出

```bash
# 交互式选择聊天导出
python qce_api.py --export

# 或使用统一工具
python comfyui_tool.py --qce-export
```

### API 调用

```bash
# 测试连接
python qce_api.py --test

# 列出所有聊天
python qce_api.py --list

# 只列出群聊
python qce_api.py --groups

# 只列出好友
python qce_api.py --friends

# 获取状态
python qce_api.py --status
```

### 导出格式

支持多种导出格式：
- **JSON** - 结构化数据，适合程序处理
- **Excel** - 表格格式，方便查看
- **HTML** - 可视化网页格式
- **Text** - 纯文本格式

### Token 获取

按 `Win + R`，输入 `%USERPROFILE%\.qq-chat-exporter` 查看 `security.json` 文件中的 `accessToken`。

### 与缓存扫描的区别

| 方式 | 说明 |
|-----|------|
| 缓存扫描 (`--scan`) | 直接扫描 QQ 缓存目录，快速提取工作流文件 |
| QCE 导出 (`--qce`) | 正规导出完整聊天记录，包含更多上下文信息 |

建议：先用 QCE 导出重要聊天，再用缓存扫描提取工作流文件。

### 相关链接

- [NapCat 官方文档](https://napneko.github.io/)
- [QQ Chat Exporter](https://github.com/shuakami/qq-chat-exporter)

## 🔍 缺失模型检测

对比工作流引用的模型与本地ComfyUI模型目录，找出缺失的模型：

```bash
python missing_model_detector.py
```

### 功能特性

- 扫描工作流JSON中引用的所有模型
- 扫描本地ComfyUI models目录（checkpoints, loras, vae等）
- 对比找出缺失的模型列表
- 生成HTML和CSV报告

### 配置本地模型目录

编辑脚本中的 `LOCAL_MODEL_BASE` 为你的实际ComfyUI模型路径：

```python
LOCAL_MODEL_BASE = Path("F:/ComfyUI/models")  # 修改为实际路径
```

### 模型目录映射

| 模型类型 | ComfyUI子目录 |
|---------|--------------|
| checkpoint | models/checkpoints/ |
| lora | models/loras/ |
| vae | models/vae/ |
| clip | models/clip/ |
| controlnet | models/controlnet/ |
| upscale_model | models/upscale_models/ |
| unet | models/unet/ |

### 输出文件

- `missing_models_report.html` - HTML可视化报告
- `missing_models.csv` - CSV格式缺失模型列表

### 统计示例

```
工作流引用模型: 731 个
本地已有模型: 245 个
缺失模型: 486 个 (66.5%)
已有模型: 245 个 (33.5%)
```

## 🛠️ 统一CLI工具

所有功能整合到一个CLI工具，方便批量执行：

```bash
python comfyui_tool.py --all
```

### 可用命令

| 参数 | 功能 |
|-----|------|
| --scan | 扫描微信/QQ缓存提取工作流 |
| --models | 提取模型资源列表 |
| --media | 从媒体文件提取工作流JSON |
| --dedup | 去重已提取的文件 |
| --stats | 生成统计分析报告 |
| --missing | 检测缺失模型 |
| --web | 启动Web可视化界面 |
| --database | 导入数据到SQLite数据库 |
| --export | 导出HTML/CSV报告 |
| --qce | 启动QCE (QQ聊天导出工具) |
| --qce-export | 交互式导出QQ聊天记录 |
| --all | 执行全部流程(不含Web和QCE) |

### 单独执行

```bash
python comfyui_tool.py --stats      # 只生成统计报告
python comfyui_tool.py --missing    # 只检测缺失模型
python comfyui_tool.py --web        # 启动Web界面
python comfyui_tool.py --qce        # 启动QCE
python comfyui_tool.py --qce-export # 导出QQ聊天记录
python comfyui_tool.py --stats --missing  # 同时执行多个
```

## 🌐 Web可视化界面

启动Web界面查看和搜索工作流：

```bash
python web_visualizer.py
# 或
python comfyui_tool.py --web
```

### 功能特性

- 查看所有工作流列表
- 搜索节点类型/模型名称
- 查看统计报告
- 查看缺失模型报告
- API接口支持自定义查询

### 访问地址

```
http://localhost:8080
```

### API接口

| 接口 | 说明 |
|-----|------|
| `/api/workflows` | 获取工作流列表 |
| `/api/search?q=KSampler&type=node` | 搜索节点/模型 |
| `/api/models` | 获取模型资源列表 |
| `/api/media_mapping` | 获取媒体映射表 |
| `/api/workflow_detail?file=xxx.json` | 获取工作流详情 |

## 💾 SQLite数据库存储

将工作流数据导入SQLite数据库，便于查询和分析：

```bash
python database_manager.py
# 或
python comfyui_tool.py --database
```

### 数据库表结构

| 表名 | 说明 |
|-----|------|
| workflows | 工作流文件列表 |
| nodes | 节点引用记录 |
| model_references | 模型引用记录 |
| model_resources | 模型资源列表 |
| media_mappings | 媒体映射表 |
| statistics | 统计信息汇总 |

### 数据库文件

```
comfyui_workflows.db
```

### 查询示例

```sql
-- 查询复杂工作流
SELECT * FROM workflows WHERE node_count > 50;

-- 查询热门节点
SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type ORDER BY COUNT(*) DESC LIMIT 10;

-- 查询模型引用
SELECT model_type, model_name, COUNT(*) FROM model_references GROUP BY model_name ORDER BY COUNT(*) DESC;
```

## 📊 报告导出

导出综合HTML报告和Excel兼容的CSV报告：

```bash
python export_reports.py
# 或
python comfyui_tool.py --export
```

### 输出报告

| 文件 | 说明 |
|-----|------|
| comprehensive_report.html | 综合分析HTML报告 |
| report_workflows.csv | 工作流列表 |
| report_nodes.csv | 节点统计 |
| report_models.csv | 模型引用统计 |
| report_media_mapping.csv | 媒体映射表 |

### 报告内容

- 总体统计（工作流数、节点数、模型引用数）
- 热门节点排行 (Top 50)
- 热门模型排行 (Top 50)
- 模型类型分布
- 工作流复杂度分布
- 最近添加的工作流

## 🖥️ Windows桌面版（GUI工具）

提供带图形界面的Windows桌面应用，无需命令行操作：

### 编译打包

```bash
# 安装PyInstaller
pip install pyinstaller

# 打包成exe
python build_exe.py
```

### 输出文件

编译后生成：
- `dist/ComfyUI工具.exe` - Windows可执行文件
- `dist/使用说明.txt` - 使用说明文档

### GUI功能

| 功能 | 说明 |
|-----|------|
| 扫描路径配置 | 支持添加多个扫描目录，一键添加微信/QQ路径 |
| 输出目录配置 | 自定义输出目录位置 |
| 代理配置 | 设置Civitai API代理地址 |
| 功能按钮 | 扫描、提取模型、媒体工作流、统计、缺失模型、数据库、导出、Web |
| 全部执行 | 一键执行所有流程 |
| 终止任务 | 停止当前运行的任务 |
| 清空输出 | 删除所有已提取的文件 |
| 进度显示 | 实时进度条和状态信息 |
| 统计信息 | 显示工作流、模型、媒体、节点数量 |
| 运行日志 | 实时显示任务执行日志 |

### GUI界面截图

```
┌─────────────────────────────────────────────────────────┐
│ ComfyUI 工作流工具 v1.0                                  │
├─────────────────────────────────────────────────────────┤
│ 扫描路径配置                                             │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ C:/Users/xxx/Documents/WeChat Files                 │ │
│ │ C:/Users/xxx/Documents/Tencent Files                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [添加路径] [添加微信路径] [添加QQ路径] [删除选中] [清空] │
├─────────────────────────────────────────────────────────┤
│ 输出目录配置                                             │
│ 输出目录: [F:/ComfyuiCatchJson/Extracted_...] [选择目录]│
├─────────────────────────────────────────────────────────┤
│ 功能操作                                                 │
│ [扫描工作流] [提取模型] [媒体工作流] [统计分析]          │
│ [缺失模型] [导入数据库] [导出报告] [Web界面]             │
│ [全部执行]                                               │
│ [终止任务] [清空输出目录] [保存配置]                     │
├─────────────────────────────────────────────────────────┤
│ 进度                                                     │
│ █████████████████████░░░░░░░░░░ 65%                     │
│ 状态: 扫描中...                                          │
├─────────────────────────────────────────────────────────┤
│ 统计信息                                                 │
│ 工作流: 532  模型: 731  媒体: 344  节点: 9000  [刷新]   │
├─────────────────────────────────────────────────────────┤
│ 运行日志                                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [INFO] 开始扫描...                                  │ │
│ │ [INFO] 找到JSON工作流: 23                           │ │
│ │ [SUCCESS] ✓ 扫描完成                                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [清空日志] [保存日志] [打开输出目录]                     │
└─────────────────────────────────────────────────────────┘
```

### GUI使用流程

1. **配置路径**：点击"添加微信路径"或手动添加扫描目录
2. **设置输出**：选择输出目录位置
3. **保存配置**：点击"保存配置"按钮
4. **执行任务**：点击功能按钮或"全部执行"
5. **查看结果**：点击"打开输出目录"查看提取的文件
6. **查看报告**：打开HTML报告查看分析结果

## 📦 版本发布

使用GitHub Actions自动构建Windows/Mac版本并发布到Releases。

### 发布新版本

```bash
# 确保所有更改已提交并推送
git status
git push

# 运行发布脚本
python release.py
```

脚本会自动：
1. 创建新版本tag（如 v1.0 → v1.1）
2. 推送tag到GitHub
3. 触发GitHub Actions自动构建
4. 发布Windows/Mac可执行文件

### 下载地址

发布后可在GitHub Releases页面下载：
```
https://github.com/maiduongtrinh075-ui/ComfyUI-Workflows-Collection/releases
```

- **Windows**: `ComfyUI-Tool.exe`（双击运行）
- **macOS**: `ComfyUI-Tool`（首次运行可能需要授权）

### 手动发布

```bash
# 创建tag
git tag -a v1.0 -m "Release 1.0"

# 推送tag触发构建
git push origin v1.0

# 删除tag（如需修改）
git tag -d v1.0
git push origin --delete v1.0
```

### 构建进度

查看GitHub Actions构建状态：
```
https://github.com/maiduongtrinh075-ui/ComfyUI-Workflows-Collection/actions
```

构建约需5-10分钟，完成后会自动发布到Releases页面。