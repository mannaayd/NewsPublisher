FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app ./app
RUN mkdir -p data
CMD ["python", "-m", "app.main"]
