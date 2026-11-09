FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

# Same pattern as mindless_meals/Dockerfile: the venv lives outside the app
# folder so a bind mount over the code can never hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /srv/gym_log
# Dependencies first (cached layer), exactly as pinned in uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Exercise frames (33 MB) in their own layer, before anything that changes
# often. Docker stores an unchanged layer once, so every kept image version
# shares one copy. Must stay above the code COPYs. See frames/README.md.
COPY frames/ frames/

# Code, YAML data, and migrations are all baked into the image: a plan
# change is a merge plus a deploy. alembic.ini sits in the working dir so
# deploy/deploy.sh can run `alembic ...` in this image.
COPY alembic.ini ./
COPY migrations/ migrations/
COPY data/ data/
COPY app/ app/
CMD ["flask", "--app", "app", "run", "--host=0.0.0.0", "--port=8000"]
