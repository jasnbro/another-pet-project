FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

# The environment lives outside /app on purpose: compose.yml bind-mounts
# ./app over /app at runtime, which would hide a .venv built inside it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /srv/mindless_meals
# Install dependencies first (cached layer), exactly as pinned in uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

WORKDIR /app
COPY app/ .
CMD ["flask", "--app", "app", "run", "--host=0.0.0.0", "--port=8000"]
