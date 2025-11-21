# Design System

O Design System do **ERP Tests** é baseado no **Tailwind CSS** e visa garantir um visual **moderno, responsivo e coeso** em todas as telas da aplicação.

## 1. Paleta de Cores

A paleta de cores define a identidade visual do sistema:

| Nome | Uso | Código Hexadecimal | Classe Tailwind (Exemplo) |
| :--- | :--- | :--- | :--- |
| **Azul Escuro** | Principal (Botões, Navbar, Destaques) | `#002d6c` | `bg-[#002d6c]`, `text-[#002d6c]` |
| **Azure Vívido** | Secundária (Ações, Links, Ícones) | `#007da0` | `bg-[#007da0]`, `text-[#007da0]` |
| **Branco Padrão** | Fundo (Páginas, Modais) | `#ffffff` | `bg-white` |

## 2. Padrões Visuais e Componentes

Todos os componentes devem seguir um padrão visual unificado, utilizando as classes utilitárias do Tailwind CSS.

### 2.1. Layout e Fundo

*   **Fundo da Página:** Deve ser sempre o **Branco Padrão** (`#ffffff`).
*   **Navbar/Header:** Deve usar a cor **Azul Escuro** (`#002d6c`) como fundo.
*   **Responsividade:** O layout deve ser totalmente responsivo, utilizando *flexbox* e *grid* do Tailwind para adaptação a dispositivos móveis, *tablets* e *desktops*.

### 2.2. Botões

| Tipo | Cor de Fundo | Cor do Texto | Exemplo de Uso |
| :--- | :--- | :--- | :--- |
| **Primário** | Azul Escuro (`#002d6c`) | Branco (`#ffffff`) | Ações principais (Ex: Salvar, Finalizar Venda). |
| **Secundário** | Azure Vívido (`#007da0`) | Branco (`#ffffff`) | Ações secundárias (Ex: Editar, Adicionar Item). |

### 2.3. Formulários (Inputs e Fields)

*   **Design:** Deve ser limpo, com bordas sutis.
*   **Foco:** Ao focar em um campo de formulário, o *outline* ou a borda deve usar a cor **Azure Vívido** (`#007da0`) para indicar o estado ativo.

### 2.4. Menus

*   **Padrão:** Utilizar um padrão de menu lateral ou superior fixo.
*   **Cor:** Seguir a cor **Azul Escuro** (`#002d6c`) para o fundo do menu principal.

### 2.5. Fontes

*   **Prioridade:** Utilizar fontes de sistema ou uma fonte *sans-serif* limpa e altamente legível para garantir a clareza da informação.
