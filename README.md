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

### 4. 增量扫描
- 文件路径 + SHA256 哈希双重去重
- 支持中断恢复

### 5. 完善异常处理
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