# Padrões de Código

## 1. Diretrizes de Estilo

O projeto adota um conjunto rigoroso de padrões de estilo para garantir a legibilidade e a manutenibilidade do código.

### 1.1. PEP 8

Todo o código Python **deve** aderir estritamente às diretrizes da **PEP 8** (Python Enhancement Proposal 8), o guia de estilo oficial para código Python.

### 1.2. Aspas Simples

O padrão para *strings* no código Python (incluindo definições de *strings* em modelos, *views* e *templates*) é o uso de **aspas simples** (`'`).

*   **Exemplo Correto:** `'Este é um texto de string.'`
*   **Exemplo Incorreto:** `"Este é um texto de string."`

## 2. Estrutura do Django

### 2.1. Class Based Views (CBVs)

O desenvolvimento de *views* deve priorizar o uso de **Class Based Views (CBVs)** em vez de *Function Based Views* (FBVs), sempre que possível. As CBVs oferecem maior reuso de código, herança e clareza estrutural.

*   **Priorizar:** `ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView` e `TemplateView`.

### 2.2. Organização de Signals

Caso o uso de *signals* (sinais) do Django seja necessário para desacoplar a lógica, eles **devem** ser organizados da seguinte forma:

1.  Crie um arquivo chamado `signals.py` dentro da *app* correspondente.
2.  Importe e conecte os *signals* no método `ready()` da classe `AppConfig` da *app*.

*   **Exemplo de Caminho:** `inventory/signals.py`

### 2.3. Recursos Nativos

O projeto deve sempre utilizar classes, funções e recursos **nativos** do Django e Python antes de recorrer a soluções externas, mantendo o princípio de **não ser *over engineering***.
