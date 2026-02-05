# Context Firewall 方案风险评估与缓解策略

虽然"Context Firewall (反向代理)"方案实现了零侵入，但在分布式系统架构中，引入中间层必然带来新的复杂性和风险。以下是该方案的 5 大核心缺陷及其规避策略。

---

## 1. 核心风险：上下文"精神分裂" (Context Schizophrenia)
这是最严重的问题。**Clawdbot (Client) 以为它发送了 A，但 LLM 实际接收到的是 B。**

*   **场景**: Clawdbot 上传了一个 5000 行的代码文件，并期待 LLM 修改。Proxy 为了节省 Token，将该文件的中间 4000 行截断/摘要了。
*   **后果**:
    *   **LLM 幻觉**: LLM 可能根据其内部训练数据瞎编这 4000 行，或者抱怨"代码不完整"。
    *   **引用失败**: Clawdbot 下一轮对话说"请查看第 300 行"，LLM 表示"我看不到"。
    *   **Client 困惑**: Clawdbot 的本地日志显示它是把完整文件发出去的，Debug 时会非常痛苦。

### 🛡️ 规避策略
1.  **保守剪枝 (Conservative Pruning)**:
    *   **原则**: 永远不要修改 `role="user"` 的**最后一轮**消息。只修剪 `role="system"` (Prompt 优化) 和 `history` (早于 3 轮之前的对话)。
    *   **白名单**: 对包含特定标记（如代码块、文件附件）的消息，跳过压缩。
2.  **占位符与"召回"机制 (Placeholder & Recall)**:
    *   不要直接删除，而是替换为占位符：`[File content truncated by Firewall. ID: doc_123]`。
    *   **高级方案（中间人代理）**: Proxy 可以向 LLM 注入一个隐藏工具 `read_full_content(doc_id)`。如果 LLM 觉得信息不够，它会尝试调用这个工具。Proxy 拦截这个 Tool Call，**在代理层内部执行**（不转发给 Clawdbot），查阅原始数据后，再将结果喂回给 LLM。这实际上是将 Proxy 变成了一个隐形的 Agent。

---

## 2. 风险：破坏 Tool Use (工具调用) 结构
Clawdbot 高度依赖 Tool Calling (如写文件、运行终端)。

*   **场景**: Clawdbot 发送了包含 Tool Definitions 的请求。Proxy 在对其进行处理（如 Summarization）时，不小心破坏了 JSON 结构，或者删除了某些作为 Tool Call 上下文的前置消息。
*   **后果**: LLM 忘记如何使用工具，或者生成的 Tool Call 参数无效，导致 Clawdbot 执行失败。

### 🛡️ 规避策略
1.  **结构感知过滤器 (Structure-Aware Filter)**:
    *   Proxy 必须能解析 OpenAI/Anthropic 的 Payload 结构。
    *   **硬性规则**: 凡是带有 `tools`, `tool_choice` 字段的请求，或者是 `role="tool"` 的消息，**禁止进行有损压缩**。
    *   只在纯文本对话（Conversation）部分动刀。

---

## 3. 风险：流式响应 (Streaming) 的延迟与不稳定性
反向代理增加了一跳网络传输。而且 Clawdbot 使用 SSE (Server-Sent Events) 流式接收回复。

*   **场景**: Proxy 在处理 LLM 返回的数据流时，如果采用"攒够了一起发"的逻辑（为了进行后处理），会导致用户感觉首字延迟（TTFT）显著增加。如果 WebSocket/HTTP 长连接断开，会导致 Clawabot 报错重试，造成重复生成。
*   **后果**: 用户体验变差，响应卡顿。

### 🛡️ 规避策略
1.  **透明流式透传 (Pass-through Streaming)**:
    *   使用 Python 的 `yield` 机制。LLM 吐出一个 Chunk，Proxy 立刻转发一个 Chunk，**不要在 Response 阶段做缓冲**。
    *   对于 Request 阶段（Proxy 此时需要处理 Prompt），必须等 Payload 接收完整才能发给 LLM，这无法避免，但 Request 通常很快。
2.  **异步并发 (AsyncIO)**:
    *   必须使用 `FastAPI` + `uvicorn` 全异步架构。Memory 检索（I/O 密集型）必须异步执行，避免阻塞 Event Loop。

---

## 4. 风险：运维复杂性增加 (Operational Complexity)
*   **问题**: 以前用户只运行 Clawdbot。现在用户需要运行 `Clawdbot` + `Ctx-Firewall` + `VectorDB`。
*   **后果**: "怎么这都不工作？"的概率增加了 3 倍。任何一个组件挂了，整个服务就挂了。

### 🛡️ 规避策略
1.  **All-in-One Docker Compose**:
    *   提供一个 `docker-compose.yml`，一键拉起所有服务。
    *   利用 Docker 的 internal network 解决 `localhost` 端口通信问题。
2.  **故障降级 (Fallback/Circuit Breaker)**:
    *   Proxy 内部实现熔断机制。如果 VectorDB 挂了/超时了，Proxy 应该 catch 异常，记录 error log，然后**自动降级为直连模式**（即不注入记忆，原样转发请求），保证 Clawdbot 至少能"以此状态"继续工作，而不是直接报错 500。

---

## 5. 风险：隐私泄露的"转移"
*   **问题**: Clawdbot 主打本地隐私。如果你的 Proxy 使用了云端 Vector DB (如 Pinecone) 或云端 LLM 来做 Summary。
*   **后果**: 用户的隐私还是泄露了，违背了 Clawdbot 的初衷。

### 🛡️ 规避策略
1.  **坚持全本地栈**:
    *   使用嵌入式 Vector DB (如 `ChromaDB` 的本地文件模式，或简单的 `SQLite-VSS`)。
    *   如果需要用模型做 Summary，尝试调用用户本地的 Ollama/LocalAI，或者复用 Clawdbot 配置的主 LLM（但要注意这会消耗 Token，可能得不偿失，还是推荐基于规则/正则的静态处理）。

---

## 总结建议

要将这个方案落地，建议采取 **"三步走" (Walk-Run-Fly)** 策略以降低风险：

1.  **Walk (观察模式)**: Proxy 部署上线，但只做 Log 记录，不做任何修改。观察 Clawdbot 的真实请求结构，确保透传无误。
2.  **Run (轻量清洗)**: 开启 System Prompt 正则剪枝，开启故障降级。验证无副作用。
3.  **Fly (记忆挂载)**: 开启 Vector DB 注入。从"只读注入"开始。

最大的挑战在于**处理 Tool Call 和流式响应的兼容性**，这部分代码需要写得非常健壮（Defensive Programming）。
