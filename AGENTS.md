# Repository Guidelines

## Project Structure & Module Organization
- `backend/` contains Django apps, REST APIs, and Channels WebSocket services. Project settings live in `backend/ops_tool/`; terminal functionality lives in `backend/web_terminal/`.
- `frontend/src/` contains Vue 3/TypeScript code: `app/` for application orchestration, `features/` for domain modules, and `shared/` for reusable code. Preserve compatibility re-exports in older `composables/` paths when refactoring.
- Frontend assets live in `frontend/public/`, with styles in `frontend/src/styles/`. Tests live in frontend `__tests__/` directories and backend `tests.py` or `tests/` modules.
- `config/` holds local configuration; `deploy/` contains Docker, Kubernetes, and deployment scripts; `docs/` contains design and implementation notes.

## Build, Test, and Development Commands
Run frontend commands from `frontend/`:
- `npm ci` installs locked dependencies.
- `npm run dev` starts Vite with API/WebSocket proxies.
- `npm run build` creates the production bundle in `dist/`.
- `npm run test:run` runs Vitest once; `npm test` starts watch mode.

Run backend commands from `backend/` in an activated Python environment (WSL is the documented Windows workflow):
- `python -m pip install -r requirements.txt` installs dependencies.
- `python manage.py migrate` applies database migrations.
- `python manage.py test` runs Django tests; append `web_terminal.tests` to target terminal tests.
- `./start-wsl.ps1` starts Daphne from PowerShell; check its machine-specific paths first.

From the repository root, `bash deploy/scripts/compose-up.sh` initializes deployment configuration and starts Compose.

## Coding Style & Naming Conventions
Use four-space Python indentation and two-space Vue/TypeScript indentation. Follow existing TypeScript single quotes and semicolons. Name Vue components `PascalCase.vue`, composables `useSomething.ts`, and Python functions/modules `snake_case`. Prefer feature-local logic and shared utilities over expanding page components. No dedicated ESLint or Prettier configuration is present; match neighboring code.

## Testing Guidelines
Use Vitest `*.test.ts` files under `src/**/__tests__/` and Django `TestCase`/`SimpleTestCase` with `test_*` methods. Add regression tests for changed behavior and preserve existing contract/structure tests. No enforced coverage threshold is configured. Legacy `frontend/tests/*.test.mjs` use Node's test runner; some require generated `.tmp` helpers and are not included in Vitest.

## Commit & Pull Request Guidelines
Follow recent prefixes: `feat:`, `fix:`, and `docs:` with concise descriptions. Keep commits focused. PRs should describe changes, link relevant issues, report validation commands/results, and include screenshots for UI changes. Highlight migrations and configuration changes.

## Security & Configuration
Use `APP_CONFIG_FILE` for backend configuration and `config/local.app.conf` for Vite settings. Never commit credentials, databases, recordings, or runtime data; use `deploy/config/app.conf` as the deployment template.
