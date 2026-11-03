import logging
import os
from datetime import datetime
from .path_tool import get_abs_path

# 设置日志保存根目录
log_path = get_abs_path('logs')

# 若不存在文件, 则自动创建
os.makedirs(log_path, exist_ok=True)

# 设定日志格式
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s -%(filename)s:%(lineno)d - %(message)s'
)

# 定义logger函数
def get_logger(
        name: str = 'agent',
        console_level: int = logging.DEBUG,
        file_level: int = logging.DEBUG,
        log_file = None,
):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(console_handler)

    # 文件handler
    if not log_file:
        log_file = os.path.join(log_path, f"{name}_{datetime.now().strftime('%Y%m%d')}'agent.log'")  #日志文件存放位置

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(file_handler)

    return logger

# 快捷获取日志器
logger = get_logger()

if __name__ == '__main__':
    logger.info("信息日志")
    logger.error("错误日志")
    logger.warning("警告日志")
    logger.debug("调试日志")
