## 14. Lista de Tarefas

### Sprint 1: Design System e Refatoração de Configurações (5 dias)

| Tarefa | Subtarefa | Escopo e Implementação | Checklist |
| :--- | :--- | :--- | :--- |
| **T1.0** | **Setup e Padrões** | Configurar ambiente de desenvolvimento e ferramentas de *linting* (ex: *flake8*). | [ ] |
| | T1.1 | Aplicar aspas simples e PEP 8 no código base. | [ ] |
| **T2.0** | **Design System** | Definir e aplicar classes utilitárias do Tailwind para o Design System. | [ ] |
| | T2.1 | Criar classes para a paleta de cores (`#002d6c`, `#007da0`, `#ffffff`). | [ ] |
| | T2.2 | Criar componentes base (botões primário/secundário, *inputs*, *forms*) com o novo padrão visual. | [ ] |
| | T2.3 | Garantir que o fundo de páginas e modais seja `#ffffff`. | [ ] |
| **T3.0** | **Configurações** | Refatorar a aba "Sobre" para "Configurações". | [ ] |
| | T3.1 | Renomear a rota `/about/` para `/configuracoes/` em `core/urls.py`. | [ ] |
| | T3.2 | Criar a *Class Based View* (CBV) `ConfiguracoesView` em `core/views.py`. | [ ] |
| | T3.3 | Criar o *template* `core/configuracoes.html` com arquitetura responsiva. | [ ] |
| | T3.4 | Adicionar campo de seleção de impressora padrão no modelo `Company` ou em um novo modelo `ConfiguracaoSistema`. | [ ] |
| | T3.5 | Implementar a lógica de salvar a impressora padrão para o *tenant* atual. | [ ] |

### Sprint 2: Impressão e Estoque XML (7 dias)

| Tarefa | Subtarefa | Escopo e Implementação | Checklist |
| :--- | :--- | :--- | :--- |
| **T4.0** | **Impressão Automática** | Implementar o *trigger* de impressão após a finalização da venda. | [ ] |
| | T4.1 | Identificar o ponto de finalização da venda (ex: `Sales.save()` ou *view* de finalização). | [ ] |
| | T4.2 | Criar a função de impressão que lê a impressora padrão configurada. | [ ] |
| | T4.3 | Integrar a função de impressão no fluxo de finalização de venda. | [ ] |
| **T5.0** | **Entrada XML** | Desenvolver a funcionalidade de importação de estoque via XML. | [ ] |
| | T5.1 | Criar a *Class Based View* (CBV) `EstoqueXMLUploadView` em `inventory/views.py`. | [ ] |
| | T5.2 | Criar o *template* para *upload* de arquivo XML. | [ ] |
| | T5.3 | Implementar a lógica de *parsing* do XML para extrair dados de produtos/estoque. | [ ] |
| | T5.4 | Criar o *template* de **modal** com interface de planilha (Excel-like) para pré-visualização e edição. | [ ] |
| | T5.5 | Implementar a lógica de *backend* para receber os dados editados do modal e atualizar/criar o estoque (modelo `Estoque`). | [ ] |
| | T5.6 | Adicionar *signals.py* em `inventory` se necessário para a lógica de estoque. | [ ] |