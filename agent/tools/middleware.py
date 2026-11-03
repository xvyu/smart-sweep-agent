from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_community.utilities.pebblo import Runtime
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from Agent.utils.logger_handler import logger
from Agent.utils.prompt_loader import report_prompt, system_prompt


# 工具执行的监控
@wrap_tool_call
def monitor_tool(
        # 请求的数据对象
        request: ToolCallRequest,
        # 执行的函数本身
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
)-> ToolMessage | Command:
    logger.info(f"[tool| monitor]执行工具: {request.tool_call["name"]}")
    logger.info(f"[tool| monitor]传入参数: {request.tool_call["args"]}")

    try:
        result = handler(request)
        logger.info(f"[tool| monitor]工具: {request.tool_call["name"]}调用成功")
        if request.tool_call["name"] == "fill_context_for_report":
            request.runtime.context["report"] = True

        return result
    except Exception as e:
        logger.error(f"[tool| monitor]工具: {request.tool_call["name"]}调用失败, {str(e)}")
        raise e

# 在模型执行前输出日志
@before_model
def log_before_model(
        state: AgentState,  # 整个Agent智能体中的状态记录
        runtime: Runtime,  # 记录了整个执行过程中的上下文信息
):
    logger.info(f"[log_before_model]即将调用模型, 带有{len(state['messages'])}条消息")
    logger.debug(f"[log_before_model] {type(state['messages'][-1]).__name__} {state['messages'][-1].content.strip()}")

    return None


# 动态切换提示词  -- 每一次生成函数之前调用此函数
@dynamic_prompt
def report_prompt_switch(request :ModelRequest):
    if_report = request.runtime.context.get("report", False)
    if if_report:
        return report_prompt()

    return system_prompt()