FROM python:3.11-slim
RUN pip install --no-cache-dir uv==0.12.23
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --uid 10001 --create-home app
USER app
ENTRYPOINT ["rosa-turbopi"]
CMD ["chat"]
