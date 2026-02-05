# LLM Adapter for Claw

💪 **AI Context Firewall** - 为 Clawdbot 提供轻量级上下文优化与语义记忆外挂

[![CI/CD](https://github.com/aki66938/llm_adapter_claw/actions/workflows/ci.yml/badge.svg)](https://github.com/aki66938/llm_adapter_claw/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 项目概述

LLM Adapter for Claw（代号：`llm_adapter_claw`）是一个基于**反向代理模式**的上下文优化适配器，在 Clawdbot 与 LLM 提供商之间充当**AI Context Firewall**，实现：

- 🎯 **Token 节约 40-70%** - 精细化上下文管理，减少冗余传输
- 🧠 **语义级记忆检索** - 向量数据库替代文件系统，实现认知记忆
- 🔧 **零侵入集成** - 不修改 Clawdbot 源码，仅通过配置指向代理
- ⚡ **动态上下文组装** - 意图驱动，仅加载当前任务必需信息

---

## 核心特性

| 特性 | 描述 | 状态 |
|------|------|------|
| **透明代理** | 完全兼容 OpenAI/Anthropic API 格式 | 🚧 WIP |
| **Prompt 剪枝** | System Prompt 清洗 + 历史记录智能压缩 | 🚧 WIP |
| **语义记忆** | SQLite-VSS 本地向量库，隐私优先 | 🚧 WIP |
| **意图分类** | 闲聊/代码/检索/工具调用场景识别 | 🚧 WIP |
| **熔断降级** | VectorDB 故障自动回退直连模式 | 🚧 WIP |
| **可观测性** | Prometheus 指标 + 结构化日志 | 🚧 WIP |

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone git@github.com:aki66938/llm_adapter_claw.git
cd llm_adapter_claw

# 安装依赖
pip install -e ".[dev]"

# 或使用 Docker Compose
docker-compose up -d
```

### 配置 Clawdbot

编辑 Clawdbot 配置文件，将 API 端点指向 Adapter：

```json
{
  "llm_provider": "openai",
  "base_url": "http://localhost:8080/v1",
  "api_key": "sk-dummy"
}
```

### 启动服务

```bash
llm-adapter-claw
# 或
python -m llm_adapter_claw
```

---

## 架构设计

```
┌─────────────┐     ┌─────────────────────────────────────────────┐     ┌─────────────┐
│  Clawdbot   │────▶│           LLM Adapter (Proxy)               │────▶│     LLM     │
│   (Client)  │◀────│  ┌─────────┐ ┌─────────┐ ┌─────────┐       │◀────│  (Provider) │
└─────────────┘     │  │ Sanitizer│▶│Classifier│▶│Assembler │       │     └─────────────┘
                    │  └─────────┘ └─────────┘ └─────────┘       │
                    │         ▲              │                    │
                    │         └──────────────┘                    │
                    │              Memory Store (SQLite-VSS)       │
                    └─────────────────────────────────────────────┘
```

### 处理管道

1. **Sanitizer** - 结构验证，标记敏感消息（Tool Calls、Attachments）
2. **Intent Classifier** - 意图识别（闲聊/代码/检索/工具调用）
3. **Context Assembler** - 动态加载 System Prompt 模块，语义检索记忆
4. **Validator** - Token 计数对比，结构完整性检查

---

## 开发

### 项目结构

```
llm_adapter_claw/
├── src/llm_adapter_claw/    # 核心源码
│   ├── core/                # 代理核心、管道、分类器
│   ├── memory/              # 向量存储、检索、嵌入
│   ├── models/              # Pydantic 模型
│   └── utils/               # 工具函数
├── tests/                   # 测试套件
├── docs/                    # 设计文档
├── scripts/                 # 辅助脚本
└── .github/workflows/       # CI/CD 配置
```

### 运行测试

```bash
pytest
# 带覆盖率
pytest --cov=src/llm_adapter_claw --cov-report=html
```

### 代码规范

```bash
# 格式化
black src tests

# 检查
ruff check src tests
mypy src
```

---

## 文档

- [架构设计](docs/architecture/ARCHITECTURE.md) - 详细架构说明
- [部署指南](docs/deployment/DEPLOYMENT.md) - 生产环境部署
- [配置参考](docs/configuration/CONFIGURATION.md) - 完整配置选项
- [设计文档](docs/) - 原始设计文档

---

## 版本更新记录

| 版本 | 日期 | 变更内容 | 提交者 |
|------|------|----------|--------|
| 0.2.0 | 2026-02-05 | 核心处理管道：意图分类、上下文组装、请求优化、流式响应（18个模块，均<500行） | 阿凯 💪 |
| 0.1.0 | 2026-02-05 | 文档补充：添加分析报告、设计方案、风险评估三篇核心设计文档 | 阿凯 💪 |
| 0.1.0 | 2026-02-05 | 项目初始化：基础架构搭建、CI/CD 配置、项目结构创建 | 阿凯 💪 |

---

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx
- **Vector DB**: SQLite-VSS (默认本地)
- **嵌入模型**: sentence-transformers
- **配置管理**: Pydantic Settings
- **监控**: Prometheus Client
- **日志**: structlog

---

## 贡献

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

---

## 许可证

[MIT License](LICENSE)

---

💪 *Built with precision. Optimized for efficiency.*
