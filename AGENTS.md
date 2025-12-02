# AGENTS - ERP FortTech

## Documentos-base
- PRD: `docs/PRD.md`.
- Arquitetura técnica: `docs/Arquitetura T‚cnica.md`.
- Padrões de código: `docs/Padräes de C¢digo.md`.
- Design System: `docs/Design System.md`.
- Planejamento: `docs/14. Lista de Tarefas.md`.
- Consulte `docs/README.md` ao iniciar qualquer trabalho para manter alinhamento com o desenho original do produto.

## Estrutura e organização
- Monolito Django 5; entrypoint `manage.py`; settings em `p_v/settings.py`.
- Apps de domínio na raiz: `p_v_App` (tenancy/middleware), `accounts`, `core`, `catalog`, `sales`, `orders`, `inventory`, `tables`, `staff`; cada um guarda `migrations/`, `templates/<app>/` e utilitários próprios.
- Templates compartilhados em `templates/`; estáticos em `static/p_v_App/assets` (coletados para `staticfiles`).
- Siga os fluxos e limites descritos na documentação antes de alterar regras de negócio.

## Setup e comandos
- Criar ambiente: `python -m venv .venv && .\\.venv\\Scripts\\activate && pip install -r requirements.txt`.
- Migrações: `python manage.py makemigrations` e `python manage.py migrate`.
- Servidor local: `python manage.py runserver 0.0.0.0:8000`.
- Testes: `python manage.py test` (ou direcionado, ex.: `python manage.py test sales.tests`).
- Release: `python manage.py collectstatic --noinput` e criar admin com `python manage.py createsuperuser` para QA manual.

## Padrões de código
- PEP 8; 4 espaços; `snake_case` para funções/variáveis e `PascalCase` para classes; arquivos em minúsculas com underscore.
- Priorize CBVs conforme Padrões de Código; lógica de negócio em serviços/modelos, não em views/templates.
- Respeite fluxo de middleware em `p_v_App/middleware*.py`; evite regras de negócio em templates (use partials com `_` no nome).
- Use aspas simples por padrão; prefira funções pequenas e composáveis; docstrings apenas quando a intenção não for óbvia.

## Testes
- Testes em `tests.py` de cada app (divida em módulos se crescerem).
- Cubra regras críticas: descontos, estoque, isolamento de tenant, middleware; adicione testes de integração para pedidos/vendas.
- Nomeie testes de forma descritiva (`test_updates_stock_on_confirmed_order`); mantenha fixtures/factories próximas ao app.
- Rode a suíte antes de push e após mudanças de esquema ou novas migrações.

## Commits e PRs
- Mensagens no imperativo com escopo curto (`feat(sales): handle combo discounts`); uma preocupação por commit quando possível.
- PRs devem trazer resumo, racional, ID da tarefa, notas de migração/dados, screenshots de UI e resultado de testes (`python manage.py test`).
- Se alterar docs ou config, cite arquivos tocados (ex.: `docs/Design System.md`, `p_v/settings.py`) e passos operacionais.

## Segurança e configuração
- Não versionar segredos; definir `SECRET_KEY`, `DATABASE_URL` etc. via variáveis de ambiente (`dj_database_url` faz override).
- Em produção, usar `DEBUG=False`, ajustar `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` para o domínio alvo.
- Ao adicionar estáticos, valide o output do `collectstatic` e caminhos do WhiteNoise.
