FROM python:3.11-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.12.23
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    XDG_CACHE_HOME="/data/.cache" \
    YOLO_CONFIG_DIR="/data/.config/Ultralytics" \
    MPLCONFIGDIR="/data/.config/matplotlib"
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd --gid ${APP_GID} app \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home app \
    && mkdir -p /data/weights /data/.cache /data/.config \
    && chown -R app:app /data
WORKDIR /data
USER app
ENTRYPOINT ["rosa-turbopi"]
CMD ["chat"]
