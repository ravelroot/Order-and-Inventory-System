<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="img/logo/logo-escuro.svg">
    <img src="img/logo/logo-claro.svg" alt="Logo do Doca" width="72">
  </picture>
</p>

# Publicar no GitHub sem expor dados pessoais

Siga na ordem. Cada fase termina com uma conferência.

## Fase 1 — Proteger o seu e-mail nos commits

Todo commit leva nome e e-mail de quem fez. Use o endereço privado que o GitHub oferece.

1. No GitHub: **Settings → Emails**.
2. Marque **Keep my email addresses private** e **Block command line pushes that expose my email**.
3. Copie o endereço que aparece, no formato `12345678+seu-usuario@users.noreply.github.com`.
4. No terminal, dentro da pasta do projeto:

   ```bash
   git init
   git config user.name "seu-usuario-do-github"
   git config user.email "12345678+seu-usuario@users.noreply.github.com"
   ```

   Conferência: `git config user.email` mostra o endereço `noreply`.

## Fase 2 — Conferir o que vai ser enviado

1. Rode `git status --ignored`.
2. Na lista **Ignored files** devem aparecer `dados/`, `.venv/` e, se existir, `.env`.
3. Na lista de arquivos a enviar **não** pode aparecer nenhum `.env`, `.db`, `credenciais_demo.txt` nem `senha_inicial_admin.txt`.

   Conferência extra (não deve listar nada):

   ```bash
   git ls-files --others --exclude-standard | findstr /i "dados .env .db senha credenciais"
   ```

   No Linux/macOS troque `findstr /i` por `grep -iE`.

## Fase 3 — Primeiro commit e envio

1. Crie um repositório **vazio** no GitHub (sem README, sem licença).
2. Envie:

   ```bash
   git add .
   git commit -m "Sistema de pedidos e controle de estoque"
   git branch -M main
   git remote add origin https://github.com/seu-usuario/sistema-pedidos-estoque.git
   git push -u origin main
   ```

   Conferência: a aba **Actions** do repositório mostra o CI rodando.

## Fase 4 — Ajustes opcionais

- Em **Settings → Code security**, ative *Secret scanning* e *Push protection*.
- Para exibir o selo do CI no README, adicione no topo:
  `![CI](https://github.com/seu-usuario/sistema-pedidos-estoque/actions/workflows/ci.yml/badge.svg)`
- Se quiser seu nome na licença, edite a linha de copyright em `LICENSE`.

## O que este projeto já faz por você

- Nenhum IP, e-mail, nome ou caminho de computador real está no código.
- Senhas e chaves nunca ficam em arquivos versionados: são geradas na hora e salvas em `dados/`, que o Git ignora.
- O servidor de desenvolvimento escuta só em `127.0.0.1` e o Docker Compose publica as portas só para o próprio computador.
- O servidor não grava IP de quem acessa e não informa a versão do Uvicorn nos cabeçalhos.
- As capturas de tela em `docs/img/` mostram apenas dados fictícios.
