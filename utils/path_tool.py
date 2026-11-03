"""
为整个工程提供统一的文件路径
"""

import os

def get_project_dir():
    """
    获取工程的根目录的绝对路径
    :return: 工程根目录
    """
    # 当前文件的绝对路径
    file_path = os.path.abspath(__file__)
    # 获取工程的根目录, 先获取文件所在的文件夹绝对路径
    current_dir = os.path.dirname(file_path)
    # 获取工程的根目录
    project_dir = os.path.dirname(current_dir)
    return project_dir

def get_abs_path(file_path):
    """
    获取当前工程内文件的绝对路径
    :param file_path: 当前文件提供的相对路径
    :return: 当前文件的绝对路径
    """
    project_dir = get_project_dir()
    abs_file_path = os.path.join(project_dir, file_path)
    return abs_file_path

if __name__ == '__main__':
    get_path = get_abs_path("history\message.txt")
    print(get_path)