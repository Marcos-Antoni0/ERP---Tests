# Repository Guidelines

## Project Structure & Module Organization
- Django 5 monolith; settings live in `p_v/settings.py`, entrypoint is `manage.py`.
- Domain apps sit at the repo root (`p_v_App` for tenancy/session middleware, `accounts`, `core`, `catalog`, `sales`, `orders`, `inventory`, `tables`, `staff`). Each app keeps its own `migrations/`, `templates/<app>/`, and optional utilities.
- Shared templates can go under `templates/` (added in `TEMPLATES[DIRS]`); static assets are under `static/p_v_App/assets` and collected to `staticfiles` for deploys.
- Product docs and constraints are in `docs/` (PRD, architecture, design system, coding standards) and should be read before changing flows.

## Build, Test, and Development Commands
- Set up env: `python -m venv .venv && .\\.venv\\Scripts\\activate && pip install -r requirements.txt`.
- Migrations: `python manage.py makemigrations` then `python manage.py migrate`.
- Run locally: `python manage.py runserver 0.0.0.0:8000`.
- Tests: `python manage.py test` (or `python manage.py test sales.tests` for targeted runs).
- Release prep: `python manage.py collectstatic --noinput`; create an admin for manual QA with `python manage.py createsuperuser`.

## Coding Style & Naming Conventions
- Python: 4-space indent; snake_case for functions/variables; PascalCase for models/forms/views classes; keep file names lowercase with underscores.
- Keep business logic inside app services/models, not views/templates; respect existing middleware flow in `p_v_App/middleware*.py`.
- Templates: name partials with a leading `_` and place under the owning app’s template folder; avoid inline business rules in templates.
- Follow project specifics in `docs/Padrões de Código.md`; prefer small, composable functions with docstrings only when intent is not obvious.

## Testing Guidelines
- Default Django test runner; tests live in each app’s `tests.py` (split into modules if they grow).
- Write unit tests for model/business rules (discounts, stock checks, tenant isolation) and middleware behaviors; add integration tests around critical order/sale flows.
- Use descriptive test names (`test_updates_stock_on_confirmed_order`); keep fixtures/app factories close to the app under test.
- Run tests before pushing and after schema changes or new migrations.

## Commit & Pull Request Guidelines
- Commit messages in imperative mood with a short scope: `feat(sales): handle combo discounts`; one concern per commit when possible.
- PRs should include: summary of change and rationale, linked issue/task ID, notes on migrations/data impacts, screenshots for UI changes, and test results (`python manage.py test`).
- If touching docs or config, note which files were updated (e.g., `docs/Design System.md`, `p_v/settings.py`) and any operational steps required.

## Security & Configuration Tips
- Do not commit secrets; set `SECRET_KEY`, `DATABASE_URL`, and other credentials via env vars (settings uses `dj_database_url` overrides).
- For deployments set `DEBUG=False`, update `ALLOWED_HOSTS`, and ensure `CSRF_TRUSTED_ORIGINS` covers the target domain.
- When adding static assets, verify `collectstatic` output and that WhiteNoise paths remain valid.
