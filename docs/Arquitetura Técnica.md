# Arquitetura Técnica

## 1. Stack Tecnológica

O projeto **ERP Tests** é construído sobre uma arquitetura *full-stack* robusta, utilizando o *framework* Django para o *backend* e *frontend* (via *Template Language*), com estilização moderna provida pelo Tailwind CSS.

| Componente | Tecnologia | Detalhes |
| :--- | :--- | :--- |
| **Backend** | Python | Linguagem de programação principal. |
| **Framework** | Django | Framework *full-stack* (incluindo *Template Language*). |
| **Frontend** | Django Template Language (DTL) | Renderização do *frontend*. |
| **Estilização** | Tailwind CSS | Framework CSS utilitário para design moderno e responsivo. |
| **Banco de Dados** | PostgreSQL | Banco de dados relacional, configurado via `dj_database_url` (ambiente Railway). |
| **Multi-tenancy** | Custom Middleware | Implementação via `TenantMiddleware` e `TenantMixin` para isolamento de dados por empresa. |

## 2. Modelo de Multi-Tenancy

O sistema suporta múltiplas empresas (tenants) em uma única instância de aplicação e banco de dados.

### 2.1. Componentes Chave

*   **`Company` (Modelo):** Representa a empresa (tenant) no sistema.
*   **`UserProfile` (Modelo):** Estende o `User` padrão do Django, associando-o a uma `Company`.
*   **`TenantMixin` (Mixin):** Classe abstrata que adiciona o campo `company` a todos os modelos de negócio que precisam ser isolados por tenant (ex: `Category`, `Products`, `Sales`).
*   **`TenantManager` (Manager):** Manager personalizado que filtra automaticamente os *querysets* pela `company` atual.
*   **`TenantMiddleware` (Middleware):** Middleware que identifica a empresa do usuário logado (`request.user.profile.company`) e a define no contexto da requisição (`request.current_company`). Ele também configura os *managers* dos modelos para aplicar o filtro de tenant automaticamente.

### 2.2. Isolamento de Dados

O isolamento é garantido pela filtragem em nível de *queryset* e pela obrigatoriedade de associar um objeto a uma `company` antes de salvar, conforme implementado no `TenantMixin` e `TenantMiddleware`.

## 3. Estrutura de Apps do Django

O projeto segue uma estrutura modular, com as seguintes *apps* principais:

| App | Responsabilidade |
| :--- | :--- |
| `p_v_App` | Configurações centrais, modelos de *multi-tenancy* e *middlewares*. |
| `accounts` | Gerenciamento de autenticação e perfis de usuário. |
| `core` | Funcionalidades centrais e *views* genéricas (ex: Home, About/Configurações). |
| `catalog` | Gerenciamento de produtos e categorias. |
| `sales` | Processamento de vendas e transações. |
| `orders` | Gerenciamento de pedidos (possivelmente pedidos de mesa ou delivery). |
| `inventory` | Gerenciamento de estoque e movimentações. |
| `tables` | Gerenciamento de mesas (para restaurantes). |
| `staff` | Gerenciamento de funcionários e permissões. |
