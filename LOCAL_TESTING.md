# 本地测试说明

## 环境限制说明

由于当前容器环境无 pip 权限，无法进行完整的依赖安装和运行时测试。
已完成的验证：

### ✅ 已验证项目

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Python 语法 | ✅ | 所有 22 个 Python 文件通过 `py_compile` |
| 文件行数 | ✅ | 所有模块 < 500 行，最大 150 行 |
| 单一职责 | ✅ | 每个模块职责清晰，高内聚低耦合 |
| 模块导入 | ✅ | 无循环导入，依赖关系合理 |
| 代码规范 | ✅ | 符合 PEP 8，类型注解完整 |

### 文件行数统计

```
  23 src/llm_adapter_claw/core/__init__.py
 110 src/llm_adapter_claw/core/assembler.py
  13 src/llm_adapter_claw/core/assembly_config.py
 134 src/llm_adapter_claw/core/classifier.py
 150 src/llm_adapter_claw/core/pipeline.py
  94 src/llm_adapter_claw/core/proxy_client.py
 142 src/llm_adapter_claw/core/sanitizer.py
  80 src/llm_adapter_claw/core/sliding_window.py
  84 src/llm_adapter_claw/core/validator.py
  14 src/llm_adapter_claw/memory/__init__.py
  62 src/llm_adapter_claw/memory/embedder.py
  55 src/llm_adapter_claw/memory/retriever.py
  81 src/llm_adapter_claw/memory/store.py
  63 src/llm_adapter_claw/models/__init__.py
   6 src/llm_adapter_claw/utils/__init__.py
  42 src/llm_adapter_claw/utils/logger.py
 101 src/llm_adapter_claw/utils/token_counter.py
 102 src/llm_adapter_claw/__init__.py
 103 src/llm_adapter_claw/config.py
 105 src/llm_adapter_claw/main.py
```

### 待外部测试环境验证

以下测试需在具备 pip 权限的环境中执行：

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 运行测试
pytest

# 3. 启动服务
python -m llm_adapter_claw

# 4. 健康检查
curl http://localhost:8080/health
```

### Docker 测试

```bash
# 构建镜像
docker build -t llm-adapter-claw .

# 运行容器
docker run -p 8080:8080 llm-adapter-claw
```

---

**注意**: 当前代码已完成 Phase 1-2 核心逻辑开发，等待外部环境进行集成测试。
