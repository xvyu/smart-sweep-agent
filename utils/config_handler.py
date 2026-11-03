"""
yaml
以k:v的形式
"""

import yaml
from .path_tool import get_abs_path

def log_rag_config(config_path: str = get_abs_path('config/rag.yaml'), encoding = 'utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)  # FullLoader 全量加载

def log_chroma_config(config_path: str = get_abs_path('config/chroma.yaml'), encoding = 'utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)  # FullLoader 全量加载

def log_prompt_config(config_path: str = get_abs_path('config/prompt.yaml'), encoding = 'utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)  # FullLoader 全量加载

def log_agent_config(config_path: str = get_abs_path('config/agent.yaml'), encoding = 'utf-8'):
    with open(config_path, 'r', encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)  # FullLoader 全量加载


rag_conf = log_rag_config()
chroma_conf = log_chroma_config()
prompt_conf = log_prompt_config()
agent_conf = log_agent_config()

if __name__ == '__main__':
    print(rag_conf['chat_model'])
