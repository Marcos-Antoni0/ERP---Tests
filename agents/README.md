# Agentes de Desenvolvimento de Software

Esta pasta contém a documentação dos Agentes de Inteligência Artificial especializados na *stack* do projeto **ERP Tests**. Cada agente possui um perfil, responsabilidades e ferramentas específicas para otimizar o processo de desenvolvimento e garantir a qualidade do código.

## Índice de Agentes

| Agente | Perfil | Ferramenta Principal | Quando Usar |
| :--- | :--- | :--- | :--- |
| [**Backend Django**](backend_django.md) | Especialista em Django, CBVs e *Multi-Tenancy*. | MCP Server `context7` | Implementação de lógica de *backend*, modelos de dados e *views* (CBVs). |
| [**Frontend Tailwind**](frontend_tailwind.md) | Especialista em DTL, Tailwind CSS e Design System. | MCP Server `context7` | Implementação do *frontend*, estilização, responsividade e aplicação do Design System. |
| [**QA / Tester**](qa_tester.md) | Especialista em Testes, Validação de Design e Funcionalidade. | MCP Server `playwright` | Criação e execução de testes de integração, validação de design e usabilidade. |
| [**Product Owner (PO)**](product_owner.md) | Especialista em Produto, Requisitos e Priorização. | PRD.md, TASKS.md | Definição de escopo, priorização de tarefas e esclarecimento de requisitos. |

---

## Uso dos Agentes

Os agentes de implementação técnica (**Backend Django** e **Frontend Tailwind**) devem utilizar o **MCP Server `context7`** para escrever código atualizado e baseado nas documentações das tecnologias da *stack* (Django, Python, Tailwind).

O agente de testes (**QA / Tester**) deve utilizar o **MCP Server `playwright`** para acessar o sistema, simular interações de usuário e verificar se o design e a funcionalidade estão conforme o esperado e os Critérios de Aceite do PRD.
