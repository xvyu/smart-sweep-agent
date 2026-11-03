"""
智扫通 · Web 适配层（BFF）

本包**只读**调用既有后端（agent/ rag/ utils/ model/），不修改任何原有逻辑。
职责：把 LangChain Agent 的 ReAct 过程翻译成前端可消费的 SSE 事件流。

运行前提（重要）：
  1) sys.path 必须包含项目根目录 D:\\Pycharm(project)，因为后端使用 `from Agent.xxx` 绝对导入；
  2) 工作目录必须是 Agent/，因为 chroma_db / data / md5.txt 都是相对路径；
  3) 需要环境变量 DEEPSEEK_API_KEY（DeepSeek 模型）与可访问的 Ollama（qwen3-embedding:4b 向量化）。
以上三点由 bootstrap.py 在导入前统一保证。
"""

__version__ = "1.0.0"
