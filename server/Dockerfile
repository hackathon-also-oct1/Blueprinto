# Server image for Azure Container Apps (or any container host)
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --extra cosmos
COPY . .
EXPOSE 7860
CMD ["uv", "run", "--no-dev", "bot.py", "--host", "0.0.0.0", "--port", "7860"]
