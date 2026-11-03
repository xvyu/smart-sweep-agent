FROM python:3.13-slim

# 代码/app/Agent/
WORKDIR /app

# 复制依赖清单
COPY requirements-api.txt ./Agent/
RUN pip install --no-cache-dir -r ./Agent/requirements-api.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 整个构建上下文
COPY . ./Agent/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 运行时 cwd 必须是 /app/Agent：chroma.yaml 里的相对路径依赖它
WORKDIR /app/Agent

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/api/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "zsapi.app:app", "--host", "0.0.0.0", "--port", "8010"]
