# Documento de Requisitos do Produto (PRD) - ERP Tests

## 1. Visão Geral

Este Documento de Requisitos do Produto (PRD) detalha as especificações e os requisitos para a evolução do sistema ERP (Enterprise Resource Planning) de teste, atualmente hospedado no repositório **ERP---Tests**. O objetivo principal é aprimorar a usabilidade, a arquitetura e adicionar funcionalidades críticas para o gerenciamento de estoque e vendas, mantendo uma abordagem de desenvolvimento *full-stack* com Django e Tailwind CSS.

## 2. Sobre o Produto

O produto é um sistema ERP desenvolvido em Python e Django, focado em atender às necessidades de **comerciantes e restaurantes** em geral. Ele é projetado para gerenciar operações essenciais como vendas, pedidos, catálogo, estoque e administração de usuários, operando em um modelo de *multi-tenancy* (múltiplas empresas) com banco de dados PostgreSQL.

## 3. Propósito

O propósito deste projeto é transformar o ambiente de teste em uma base sólida e funcional, implementando melhorias de design, arquitetura e funcionalidades específicas que são cruciais para o público-alvo, como a entrada de estoque via XML e a impressão automática de vendas.

## 4. Público Alvo

O público-alvo primário são **proprietários e gerentes de pequenos e médios comerciantes e restaurantes** que necessitam de um sistema de gestão simples, eficiente e com baixo *over engineering*. O sistema deve ser intuitivo e totalmente em **Português Brasileiro**.

## 5. Objetivos

| ID | Objetivo | Descrição |
| :--- | :--- | :--- |
| O-01 | **Melhoria da Usabilidade** | Implementar um Design System coeso e moderno, garantindo que todas as telas sejam responsivas e sigam um padrão visual unificado. |
| O-02 | **Otimização da Arquitetura** | Refatorar a seção de configurações para uma arquitetura organizada e responsiva, utilizando *Class Based Views* (CBVs) e recursos nativos do Django. |
| O-03 | **Funcionalidade Crítica de Estoque** | Adicionar a funcionalidade de entrada de estoque via arquivo XML, com pré-visualização e edição em formato de planilha (modal semelhante ao Excel). |
| O-04 | **Funcionalidade Crítica de Vendas** | Implementar a impressão automática de vendas finalizadas na impressora padrão configurada. |
| O-05 | **Conformidade Técnica** | Garantir que o código siga os padrões da **PEP 8** e utilize aspas simples consistentemente. |

## 6. Ajustes

| ID | Ajuste | Detalhamento | Status Atual |
| :--- | :--- | :--- | :--- |
| A-01 | **Substituição de Aba** | Substituir a aba "Sobre" (`/about/`) do Navbar pela aba **"Configurações"**. | A rota `/about/` existe em `core/urls.py` e `core/views.py`. Deve ser renomeada e refatorada. |
| A-02 | **Localização** | Toda a informação da interface do usuário deve estar em **Português Brasileiro**. | O projeto já utiliza `LANGUAGE_CODE = 'pt-br'` e `TIME_ZONE = 'America/Sao_Paulo'` em `settings.py`. |
| A-03 | **Estilo de Código** | Uso obrigatório de **aspas simples** e aderência estrita à **PEP 8**. | Requer revisão e refatoração do código existente. |
| A-04 | **Estrutura Django** | Priorizar o uso de **Class Based Views (CBVs)**, classes, funções e recursos nativos do Django. | O projeto já utiliza CBVs em algumas *apps*, mas deve ser um padrão. |
| A-05 | **Signals** | Se utilizados, os *signals* devem ser alocados em um arquivo `signals.py` dentro da *app* correspondente. | Requer verificação e aplicação do padrão. |

## 7. Requisitos de Novas Funcionalidades

### 7.1. Configurações do Sistema (Substituição da Aba "Sobre")

A nova aba "Configurações" deve ser o ponto central para ajustes específicos da empresa (tenant).

**Requisitos:**
*   **RFN-01:** Criar a estrutura de *views* e *templates* para a aba "Configurações".
*   **RFN-02:** A aba deve ser organizada e **responsiva**, com uma boa arquitetura (ex: abas laterais, cards).
*   **RFN-03:** Deve conter um campo para **escolher a impressora padrão** para o *tenant* atual.
*   **RFN-04:** Deve ser criado o conteúdo estático e as funções necessárias para o gerenciamento de configurações.

### 7.2. Impressão Automática de Vendas

**Requisitos:**
*   **RFN-05:** Implementar um mecanismo que, ao finalizar uma venda (`Sales` ou `Pedido`), dispare imediatamente o comando de impressão.
*   **RFN-06:** A impressão deve ser direcionada para a impressora mapeada no campo de configurações (RFN-03).

### 7.3. Entrada de Estoque via XML

**Requisitos:**
*   **RFN-07:** Criar uma *view* e *template* para a funcionalidade de "Entrada de Estoque via XML" dentro da *app* `inventory`.
*   **RFN-08:** O usuário deve poder carregar um arquivo XML (provavelmente uma Nota Fiscal Eletrônica - NFe).
*   **RFN-09:** O sistema deve extrair as informações relevantes do XML (código do produto, nome, quantidade, preço, custo, etc.).
*   **RFN-10:** Após a extração, um **modal** deve ser exibido, apresentando os dados em formato de planilha (semelhante ao Excel), permitindo que o usuário **modifique** os dados antes de confirmar a entrada no estoque.
*   **RFN-11:** A confirmação do modal deve realizar a atualização ou criação dos itens de estoque (modelo `Estoque` em `p_v_App/models.py`).

### 7.4. Flowchart (Mermaid)

O fluxo de UX para a nova funcionalidade de **Entrada de Estoque via XML** é o mais crítico:

\`\`\`mermaid
graph TD
    A[Usuário acessa Entrada de Estoque] --> B{Carregar Arquivo XML};
    B --> C[Sistema processa XML];
    C --> D{Extração de Dados Sucesso?};
    D -- Sim --> E[Exibir Modal de Pré-visualização/Edição (Excel-like)];
    D -- Não --> F[Exibir Erro de Processamento];
    E --> G{Usuário Modifica/Confirma Dados};
    G -- Modifica --> E;
    G -- Confirma --> H[Sistema salva dados no Estoque];
    H --> I[Exibir Mensagem de Sucesso];
    F --> I;
    I --> J[Retornar para a tela de Estoque];
\`\`\`

## 8. Requisitos Não-Funcionais

| Categoria | ID | Requisito |
| :--- | :--- | :--- |
| **Usabilidade** | RNF-01 | O sistema deve ser intuitivo e fácil de usar, com curva de aprendizado mínima. |
| **Performance** | RNF-02 | As operações de CRUD (Create, Read, Update, Delete) devem ser concluídas em menos de 500ms. |
| **Segurança** | RNF-03 | O sistema deve manter a segregação de dados entre *tenants* (empresas) conforme a arquitetura *multi-tenancy* atual. |
| **Manutenibilidade** | RNF-04 | O código deve ser limpo, bem documentado e seguir os padrões de estilo (PEP 8, aspas simples). |
| **Design** | RNF-05 | O design deve ser **moderno e responsivo**, adaptando-se a diferentes tamanhos de tela (desktop, tablet, mobile). |

## 9. Arquitetura Técnica

### 9.1. Stack

| Componente | Tecnologia | Detalhes |
| :--- | :--- | :--- |
| **Backend** | Python | Linguagem de programação principal. |
| **Framework** | Django | Framework *full-stack* (incluindo *Template Language*). |
| **Frontend** | Django Template Language (DTL) | Renderização do frontend. |
| **Estilização** | Tailwind CSS | Framework CSS utilitário para design moderno e responsivo. |
| **Banco de Dados** | PostgreSQL | Conexão via `dj_database_url` (Railway). |
| **Servidor** | Railway | Ambiente de hospedagem (produção). |
| **Multi-tenancy** | Custom Middleware | Implementação via `TenantMiddleware` e `TenantMixin` (isolamento de dados por empresa). |

### 9.2. Estrutura de Dados (Schemas Mermaid)

O sistema é baseado em um modelo de *multi-tenancy* onde a maioria dos modelos herda de `TenantMixin` e é filtrada pelo campo `company`.

\`\`\`mermaid
erDiagram
    COMPANY ||--o{ USER_PROFILE : possui
    USER ||--o{ USER_PROFILE : tem
    COMPANY ||--o{ CATEGORY : possui
    COMPANY ||--o{ PRODUCTS : possui
    COMPANY ||--o{ ESTOQUE : possui
    COMPANY ||--o{ SALES : possui
    COMPANY ||--o{ PEDIDO : possui
    
    COMPANY {
        int id PK
        varchar name "Nome da Empresa"
        varchar cnpj "CNPJ"
        float tax_rate "Taxa de Imposto"
        float delivery_fee "Taxa de Entrega Padrão"
    }
    
    USER {
        int id PK
        varchar username
    }
    
    USER_PROFILE {
        int id PK
        int user_id FK
        int company_id FK
        boolean is_company_admin
    }
    
    CATEGORY {
        int id PK
        int company_id FK
        varchar name
    }
    
    PRODUCTS {
        int id PK
        int company_id FK
        varchar name
        float price
        float custo
    }
    
    ESTOQUE {
        int id PK
        int company_id FK
        int produto_id FK
        int categoria_id FK
        int quantidade
        date validade
        float preco
        float custo
    }
    
    SALES {
        int id PK
        int company_id FK
        float grand_total
        date date_added
    }
    
    PEDIDO {
        int id PK
        int company_id FK
        varchar forma_pagamento
        float discount_total
    }
\`\`\`

## 10. Design System

O Design System será construído utilizando **Tailwind CSS** diretamente nos *templates* do Django, garantindo um visual moderno, limpo e responsivo.

### 10.1. Paleta de Cores

| Nome | Uso | Código Hexadecimal |
| :--- | :--- | :--- |
| **Azul Escuro** | Principal (Botões, Navbar, Destaques) | `#002d6c` |
| **Azure Vívido** | Secundária (Ações, Links, Ícones) | `#007da0` |
| **Branco Padrão** | Fundo (Páginas, Modais) | `#ffffff` |

### 10.2. Componentes e Padrões Visuais

*   **Fundo:** O fundo da página e dos modais deve ser o **Branco Padrão** (`#ffffff`).
*   **Navbar/Header:** Deve usar a cor **Azul Escuro** como fundo.
*   **Botões Primários:** Fundo **Azul Escuro** (`#002d6c`), texto branco.
*   **Botões Secundários:** Fundo **Azure Vívido** (`#007da0`), texto branco.
*   **Inputs/Forms:** Design *flat* ou com bordas sutis, foco na cor **Azure Vívido**.
*   **Grids/Layouts:** Uso de *flexbox* e *grid* do Tailwind para garantir a **responsividade** em todas as telas.
*   **Menus:** Padrão de menu lateral ou superior fixo, seguindo a cor **Azul Escuro**.
*   **Fontes:** Priorizar fontes de sistema ou uma fonte *sans-serif* limpa e legível.

## 11. User Stories

### 11.1. Épico: Configuração e Operação do Sistema

| ID | Épico |
| :--- | :--- |
| E-01 | Como Administrador da Empresa, eu quero ter uma seção de Configurações organizada para gerenciar ajustes operacionais, como a impressora padrão, para garantir o fluxo de trabalho correto. |
| E-02 | Como Gerente de Estoque, eu quero poder importar dados de estoque a partir de um arquivo XML, com a possibilidade de revisar e editar os dados antes de salvar, para agilizar a entrada de mercadorias e garantir a precisão dos dados. |
| E-03 | Como Operador de Vendas, eu quero que, ao finalizar uma venda, o comprovante seja impresso automaticamente na impressora padrão, para garantir a eficiência e o registro imediato da transação. |

### 11.2. Critérios de Aceite

| Épico | User Story | Critérios de Aceite |
| :--- | :--- | :--- |
| E-01 | Como Admin, eu posso acessar a aba "Configurações" no Navbar. | A aba "Sobre" é removida e substituída por "Configurações". A página de Configurações carrega com sucesso e é responsiva. |
| E-01 | Como Admin, eu posso selecionar e salvar uma impressora padrão. | Um campo de seleção de impressora é exibido. A seleção é persistida no banco de dados para o *tenant* atual. |
| E-02 | Como Gerente, eu posso carregar um arquivo XML na seção de Estoque. | Um botão/área de *upload* de XML é funcional. O sistema valida o formato do arquivo. |
| E-02 | Como Gerente, eu posso pré-visualizar e editar os dados do XML. | Um modal com interface de planilha é exibido com os dados extraídos. O usuário pode modificar células e confirmar a importação. |
| E-03 | Como Operador, a venda finalizada dispara a impressão. | Após a finalização da venda, o sistema envia o comando de impressão para a impressora configurada em Configurações. |

## 12. Métricas de Sucesso

| Categoria | KPI | Métrica | Meta |
| :--- | :--- | :--- | :--- |
| **Produto** | Taxa de Adoção da Funcionalidade XML | % de *tenants* que utilizam a importação XML pelo menos uma vez por mês. | > 60% |
| **Usuário** | Tempo Médio de Entrada de Estoque | Tempo gasto para completar o processo de importação XML (do *upload* à confirmação). | < 5 minutos |
| **Performance** | Latência da Impressão | Tempo entre a finalização da venda e o início da impressão. | < 2 segundos |
| **Qualidade** | Conformidade com PEP 8 | % de arquivos Python que passam na verificação de estilo (ex: `flake8`). | 100% |

## 13. Risco e Mitigações

| Risco | Descrição | Mitigação |
| :--- | :--- | :--- |
| **R-01** | Complexidade na leitura e *parsing* de diferentes formatos de XML (NFe). | Utilizar bibliotecas Python robustas para XML (*lxml* ou similar) e focar inicialmente em um subconjunto de campos essenciais. |
| **R-02** | Dificuldade na implementação da impressão automática (dependência de *drivers* ou serviços externos). | Utilizar uma solução de impressão via rede (ex: *CUPS* ou API de impressão local) e fornecer documentação clara sobre a configuração. |
| **R-03** | *Over engineering* na refatoração do Design System. | Limitar o escopo do Design System aos componentes essenciais (cores, botões, formulários) e usar o Tailwind CSS de forma utilitária. |
\`\`\`
