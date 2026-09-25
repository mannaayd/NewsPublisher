FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app ./app
RUN mkdir -p data
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os,time; p='/tmp/news-channel-bot.heartbeat'; assert os.path.exists(p) and time.time()-os.path.getmtime(p)<90"
CMD ["python", "-m", "app.main"]
