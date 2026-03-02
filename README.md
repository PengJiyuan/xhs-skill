# xhs-skill

小红书自动发布工具

## 功能

- 扫码登录一次，后续免登录
- 命令行发布笔记
- 正文 #标签 自动提取
- **AI 配图**：集成 Seedream 5.0，支持中文海报生成
- **评论互动**：自动抓取评论，AI 生成回复

## 安装

```bash
npx skills add PengJiyuan/xhs-skill
```

## 使用

```bash
# 登录
python3 scripts/xhs_auto.py login

# 发布（支持 AI 配图）
python3 scripts/xhs_auto.py publish --title "标题" --content "正文内容 #标签"

# 仅文字（不生成配图）
python3 scripts/xhs_auto.py publish --content "纯文字内容 #标签" --no-auto-image

# AI 配图（使用 Seedream 5.0）
python3 scripts/xhs_auto.py generate --prompt "描述你想要的图片"

# 评论互动
python3 scripts/comments.py fetch          # 抓取评论
python3 scripts/comments.py reply           # 自动回复
python3 scripts/comments.py reply --dry-run  # 预览回复
python3 scripts/comments.py stats          # 查看统计
```

## 配置

### 环境变量

```bash
# Seedream 5.0 API（如使用 AI 配图）
export SEEDREAM_API_URL="https://ark.cn-beijing.volces.com/api/v3/images/generations"
export SEEDREAM_MODEL="doubao-seedream-5-0-260128"
export SEEDREAM_API_KEY="your-api-key"
```

## 环境

- Python 3.9+
- Playwright

## 文件结构

```
xhs-publisher/
├── scripts/
│   ├── xhs_auto.py      # 主程序：登录、发布
│   ├── comments.py       # 评论互动
│   ├── image_gen.py    # AI 配图（Seedream 5.0）
│   ├── content_gen.py  # 内容生成
│   └── ...
├── templates/          # 封面模板
├── data/              # 数据存储
└── browser_data/     # 浏览器登录状态
```
