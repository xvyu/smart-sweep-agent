import os
import time
import httpx
import random
from Agent.utils.config_handler import agent_conf
from Agent.utils.logger_handler import logger
from Agent.utils.path_tool import get_abs_path
from langchain_core.tools import tool
from Agent.rag.rag_server import RagSummarizeServer


rag = RagSummarizeServer()
user_ids = ['1001','1002','1003','1004','1005','1006','1007','1008','1009','1010']
month_arr = ["2025-01","2025-02","2025-03","2025-04","2025-05","2025-06",
             "2025-07","2025-08","2025-09","2025-10","2025-11","2025-12"]
external_data = {}

_WEATHER_CACHE: dict[str, tuple[float, str]] = {}


def _amap_get(path: str, params: dict) -> dict:
    """调用高德 Web 服务接口；失败时抛异常，由调用方兜住"""
    key = os.environ.get("AMAP_KEY")
    if not key:
        raise RuntimeError("未配置 AMAP_KEY 环境变量")

    conf = agent_conf.get("weather") or {}
    base_url = conf.get("base_url", "https://restapi.amap.com/v3")
    timeout = conf.get("timeout", 5)

    with httpx.Client(timeout=timeout) as client:
        resp = client.get(f"{base_url}{path}", params={**params, "key": key})
        resp.raise_for_status()
        data = resp.json()

    if str(data.get("status")) != "1":
        raise RuntimeError(f"高德接口返回错误: {data.get('info')} ({data.get('infocode')})")
    return data



@tool
def rag_summarize(query:str)->str:
    """从向量存储中检索参考资料。
    Args:
        query: 用户的提问或需要检索的关键词。
    """
    return rag.rag_summarize(query)

@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气，包含天气现象、气温、湿度、风向风力。
    当用户询问某地天气、气温、是否下雨、出门是否需要带伞时调用本工具。
    Args:
        city: 中文城市名，如"深圳"、"北京市"。不要传省份名或区县名。
    Returns:
        中文天气摘要字符串；查询失败时返回提示语，不抛异常。
    """
    city = (city or "").strip()
    if not city:
        return "请提供要查询的城市名，例如：深圳"

    conf = agent_conf.get("weather") or {}
    ttl = conf.get("cache_ttl", 600)
    cached = _WEATHER_CACHE.get(city)
    if cached and time.time() - cached[0] < ttl:
        return cached[1]

    try:
        geo = _amap_get("/geocode/geo", {"address": city})
        geocodes = geo.get("geocodes") or []
        if not geocodes:
            return f"未找到城市「{city}」，请确认城市名是否正确"
        adcode = geocodes[0].get("adcode")
        if not adcode:
            return f"未能解析城市「{city}」的行政区划编码"

        weather = _amap_get("/weather/weatherInfo", {"city": adcode, "extensions": "base"})
        lives = weather.get("lives") or []
        if not lives:
            return f"暂时无法获取{city}的天气信息，请稍后再试"
        live = lives[0]

        result = (
            f"{live.get('city', city)}：{live.get('weather', '未知')}，"
            f"气温{live.get('temperature', '--')}℃，"
            f"湿度{live.get('humidity', '--')}%，"
            f"{live.get('winddirection', '')}风{live.get('windpower', '--')}级，"
            f"数据更新时间 {live.get('reporttime', '未知')}"
        )
        _WEATHER_CACHE[city] = (time.time(), result)
        logger.info(f"get_weather 成功: {city}")
        return result
    except Exception as e:
        logger.warning(f"get_weather 失败: city={city}, 原因={e}")
        return f"暂时无法获取{city}的天气信息，请稍后再试"


@tool
def get_user_location() -> str:
    """获取用户当前所在的城市名称，以纯字符串返回。
    当用户说"我这里""本地""我这边"的天气、或未指明城市需要定位时调用本工具。
    """
    conf = agent_conf.get("weather") or {}
    city = str(conf.get("default_city", "深圳")).strip()
    return city or "深圳"


@tool
def get_user_id()->str:
    """获取用户ID，以纯字符串的形式返回"""
    return random.choice(user_ids)

@tool
def get_current_month()->str:
    """获取当前月份，以纯字符串的格式返回"""
    return random.choice(month_arr)


def generate_external_data():
    """
    {
        "user_id":{
            "month":{"特征": xxx, "效率": xxx,...}
            "month":{"特征": xxx, "效率": xxx,...}
            "month":{"特征": xxx, "效率": xxx,...}
            ...
        },
        "user_id":{
            "month":{"特征": xxx, "效率": xxx,...}
            "month":{"特征": xxx, "效率": xxx,...}
            "month":{"特征": xxx, "效率": xxx,...}
            ...
        },
        "user_id":{
            "month":{"特征": xxx, "效率": xxx,...}
            "month":{"特征": xxx, "效率": xxx,...}
            "month":{"特征": xxx, "效率": xxx,...}
            ...
        },
        ...
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abs_path(agent_conf["external_data_path"])
        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部文件数据{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                arr: list[str] = line.strip().split(",")

                user_id : str = arr[0].replace('"', '')
                feature : str = arr[1].replace('"', '')
                efficiency : str = arr[2].replace('"', '')
                consumables : str = arr[3].replace('"', '')
                comparison : str = arr[4].replace('"', '')
                time : str = arr[5].replace('"', '')

                if user_id not in external_data:
                    external_data[user_id] = {}

                external_data[user_id][time] = {
                    "特征":feature,
                    "效率":efficiency,
                    "耗材":consumables,
                    "对比":comparison,
                }

@tool
def fetch_external_data(user_id:str, month:str)->str:
    """从外部系统中获取指定用户在指定月份的使用记录, 以纯字符串的形式返回, 若未检索到则返回空字符串"""
    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(f"{fetch_external_data}未能检索到到用户{user_id}在{month}本月的使用记录")
        return ""

@tool
def fill_context_for_report():
    """无入参、无出参，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息"""
    return "fill_context_for_report已调用"

if __name__ == '__main__':
    print(fetch_external_data(user_id='1001', month='2025-01'))