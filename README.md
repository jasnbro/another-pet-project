# Undercurrent on ATLAS

Self-hosted apps and the infrastructure that runs them, built and operated by Jasmine Brooks-Beltran with AI coding agents.

## Mindless Meals

A recipe and meal-planning web app that answers one question: what should I eat this week? Browse and filter recipes, save favorites, build a meal plan, and export recipes or a grocery list.

- **Stack:** Python, Flask, SQLAlchemy, Alembic, Postgres (SQLite for local dev), vanilla JavaScript, Docker Compose
- **Tests:** 45 Python tests (API, persistence, seeding) and 26 JavaScript tests (filtering, recipe form)
- **Run it locally:** no database server needed; see the [Mindless Meals README](mindless_meals/README.md)
- **Database:** schema, migrations and backups in [docs/database.md](mindless_meals/docs/database.md)

## Infrastructure

| Service | Role |
|---|---|
| `postgres/` | Shared Postgres server, one database per app, internal network only, scripted backup and restore |
| `cloudflared/` | Cloudflare tunnel for external access without open ports |
| `mindless_meals/` | The app, containerized |
| `jellyfin/` | Personal media server |

Server runbook: [docs/atlas.md](docs/atlas.md).

## How it's built with AI agents

Claude and ChatGPT act as coding agents; I own the architecture, data model, review and deploys.

- [AGENTS.md](AGENTS.md) is a checklist agents must read before working here. Each entry comes from a real mistake, such as ORM schema creation colliding with database migrations.
- AI-authored issues and PRs are labeled (`author:claude`, `author:chatgpt`) and carry a footer naming the model.
- When an agent needs a decision, it applies `status:needs-human-review`, and a GitHub Action notifies me.

## Attribution convention

- Claude and ChatGPT post through the owner's GitHub account, so the
  GitHub author is always jasnbro. Mark AI-written work explicitly.
- Issues and PRs: add the `author:claude` or `author:chatgpt` label.
- Issue bodies, PR descriptions and comments: end with a footer naming
  the model, e.g. `*Authored by Claude (Anthropic, Claude Opus 5.5)
  via the user's GitHub account.*`
- Commits: include a `Co-Authored-By:` trailer for the agent.
- No Claude Code session links anywhere in the repo (see AGENTS.md).
