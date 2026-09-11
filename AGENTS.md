# Repository Guidelines

## Project Structure & Module Organization

- `backend/` contains Django REST APIs, Channels WebSockets, and domain apps such as `host_management`, `web_terminal`, and `bulk_execution`. Project settings and ASGI entry points live in `backend/ops_tool/`; schema changes belong in each app’s `migrations/`.
- `frontend/src/` contains Vue 3 and TypeScript code. Organize feature components, composables, API clients, and utilities under `features/`; reusable code belongs in `shared/`. Existing `components/`, `composables/`, and `services/` also remain in use. Styles live in `styles/`.
- `deploy/` holds Docker, Compose, Kubernetes, and deployment scripts. `config/` contains local configuration; `docs/superpowers/` contains design specifications and implementation plans.

## Build, Test, and Development Commands

Use Linux or WSL for backend development because bulk execution depends on Ansible. Install Python dependencies in a virtual environment.

From `backend/`:

```bash
pip install -r requirements.txt
export APP_CONFIG_FILE=../config/local.app.conf
python manage.py migrate
python -m daphne -b 127.0.0.1 -p 8001 ops_tool.asgi:application
python manage.py test
```

These commands install dependencies, select local configuration, apply migrations, start HTTP/WebSocket services, and run backend tests.

From `frontend/`:

- `npm ci`: install locked dependencies.
- `npm run dev`: start Vite, normally on port 5173, with backend proxies.
- `npm run build`: generate production assets in `dist/`.
- `npm run test:run`: run Vitest once; `npm test` enables watch mode.
- `node --test tests/*.test.mjs`: run the separate Node regression tests.

From the repository root, `docker build -f deploy/Dockerfile -t devops-tools:latest .` builds the application image.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions, and `PascalCase` classes. Follow existing TypeScript conventions: two-space indentation, single quotes, and semicolons. Name Vue components `PascalCase.vue` and composables `useSomething.ts`. Prefer existing `@features` and `@shared` aliases. No dedicated formatter or linter is configured; match surrounding code.

## Testing Guidelines

Backend tests use Django `TestCase`/`SimpleTestCase`, in `tests.py` or `tests/test_*.py`, with `test_*` methods. Vitest discovers `src/**/*.test.ts`, commonly inside `__tests__/`. Add regression coverage for changed behavior and mock remote connections. No coverage threshold is configured.

## Commit & Pull Request Guidelines

History commonly uses `fix:`, `feat`, and `docs:` prefixes with English or Chinese summaries; prefer consistent `type: short description` formatting. Keep commits focused. PRs should describe behavior changes, link relevant issues, list validation performed, and include screenshots for UI changes. Call out migrations and configuration changes.

## Security & Configuration

Keep committed configuration limited to safe defaults. Deployment settings belong in ignored `data/config/app.conf`; never commit credentials, private keys, databases, uploads, or session recordings.
