from langchain.agents import create_agent
from Agent.model.factory import chat_model
from Agent.utils.prompt_loader import system_prompt
from Agent.agent.tools.agent_tools import (get_weather, rag_summarize, get_user_location, get_user_id,
                                           get_current_month, fetch_external_data, fill_context_for_report)
from Agent.agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch


class ReactAgent:
    def __init__(self) :
        self.agent = create_agent(
            model = chat_model,
            system_prompt = system_prompt(),
            tools = [get_weather, rag_summarize, get_user_location, get_user_id,
                     get_current_month, fetch_external_data, fill_context_for_report],
            middleware = [monitor_tool, log_before_model, report_prompt_switch]
        )

    def execute_stream(self, query:str):
        input_dict ={
            "messages":[
                {"role":"user","content":query}
            ]
        }

        # 第三个参数context就是上下文runtime中的信息, 就是我们做提示词切换的标记
        for chunk in self.agent.stream(input_dict, stream_mode= "values", context= {"report":False}):
            latest_message = chunk["messages"][-1]
            if latest_message.content:
                yield  latest_message.content.strip() + '\n'

if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream("扫地机器人在我所在地区的气温下该怎么保养"):
        print(chunk,end="",flush=True)