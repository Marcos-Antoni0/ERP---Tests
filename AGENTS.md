# Repository Guidelines

## Project Structure & Module Organization
- Django project: `p_v` (settings at `p_v/settings.py`, URLs at `p_v/urls.py`).
- Apps (by domain): `accounts`, `catalog`, `core`, `inventory`, `orders`, `sales`, `staff`, `tables`, `p_v_App`.
- Templates: per‑app under `*/templates/<app>/*.html` (e.g., `sales/templates/sales/pos.html`).
- Static assets: `static/` (includes `p_v_App/assets/...`).
- Tests: per‑app `tests.py` (e.g., `orders/tests.py`). Add module‑specific tests as `tests/test_<module>.py` if a file grows large.
- Management commands: `p_v_App/management/commands/` (e.g., `load_json_data.py`).

## Build, Test, and Development Commands
- Create venv (Windows PowerShell): `python -m venv .venv; .\.venv\Scripts\Activate.ps1`
- Install deps: `pip install -r requirements.txt`
- DB migrations: `python manage.py makemigrations && python manage.py migrate`
- Run server (dev): `python manage.py runserver`
- Run tests: `python manage.py test`
- Production entry (Procfile): `web: gunicorn p_v.wsgi:application`

## Coding Style & Naming Conventions
- Follow PEP 8 with 4‑space indentation and 88–100 col lines.
- Modules/apps: lowercase (`sales`, `inventory`). Classes: `CamelCase`. Functions/vars: `snake_case`. Constants: `UPPER_SNAKE`.
- Django: model classes are singular; URL namespaced as `app:name`; templates named by feature (e.g., `manage_product.html`).
- Keep business logic in `models/ utils/` where possible; views thin and tested.

## Testing Guidelines
- Use Django `TestCase` for models/views; isolate units with factories/fixtures where needed.
- Place quick tests in app `tests.py`; create `tests/` package when tests outgrow a single file.
- Name tests by behavior: `test_<action>_<expected>()`. Run all with `python manage.py test`.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `chore:`, `refactor:`, `test:`, `docs:`.
  - Examples: `feat(orders): add receipt export`, `fix(inventory): correct stock decrement on cancel`.
- PRs include: clear description, linked issues, screenshots for UI, migration notes (up/down impact), and manual test steps.

## Security & Configuration Tips
- Configure via env vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL`. Never commit secrets.
- Static files in prod served by Whitenoise; ensure `collectstatic` runs in your deployment.
- Optional seed: if relevant, run `python manage.py load_json_data` to import initial data.

