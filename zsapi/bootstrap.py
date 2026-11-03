"""
环境自举：在任何后端模块被导入之前，把运行环境修正到后端期望的状态。

后端代码依赖三个隐含前提，这里统一兜底，避免"接口起不来但报错看不懂"：

  1. `sys.path` 必须包含项目根目录（`D:\\Pycharm(project)`），
     因为所有后端模块都用 `from Agent.xxx import ...` 的绝对导入。

  2. 工作目录必须是 `Agent/`，
     因为 config/chroma.yaml 里的 `persist_directory: chroma_db`、
     `data_path: data`、`md5_hex_store: md5.txt` 全是相对路径。

  3. `DEEPSEEK_API_KEY` 必须在进程环境里。
     Windows 用户级环境变量不会自动出现在已启动的进程里，
     这里从注册表读取用户/机器级变量补齐（只读，不写回系统）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Agent/zsapi/bootstrap.py -> Agent/
AGENT_DIR = Path(__file__).resolve().parent.parent
# Agent/ -> D:\Pycharm(project)
PROJECT_DIR = AGENT_DIR.parent

_REQUIRED_KEYS = ("DEEPSEEK_API_KEY",)


def _read_windows_env(name: str) -> str | None:
    """从 Windows 用户级/机器级环境变量中读取（不依赖当前进程环境）。"""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover - 非 Windows
        return None

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    )
    for root, subkey in locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, name)
                if value:
                    return str(value)
        except OSError:
            continue
    return None


def _ensure_api_keys() -> list[str]:
    """补齐缺失的 API Key，返回实际补齐的变量名列表。"""
    filled: list[str] = []
    for key in _REQUIRED_KEYS:
        if os.environ.get(key):
            continue
        value = _read_windows_env(key)
        if value:
            os.environ[key] = value
            filled.append(key)
    return filled


def bootstrap() -> dict:
    """执行自举，返回诊断信息（供 /api/health 使用）。幂等。"""
    os.chdir(AGENT_DIR)

    project_str = str(PROJECT_DIR)
    if project_str not in sys.path:
        sys.path.insert(0, project_str)

    filled = _ensure_api_keys()

    return {
        "agent_dir": str(AGENT_DIR),
        "project_dir": project_str,
        "cwd": os.getcwd(),
        "sys_path_ok": project_str in sys.path,
        "env_filled": filled,
        "deepseek_key_present": bool(os.environ.get("DEEPSEEK_API_KEY")),
    }


# 导入本模块即生效——必须早于任何 Agent.* 的导入
BOOTSTRAP_INFO = bootstrap()
