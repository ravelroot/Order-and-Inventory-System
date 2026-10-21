import { api } from "../api.js";
import {
  abrirDialogo,
  abrirGaveta,
  aviso,
  avisarErro,
  botao,
  cabecalhoPagina,
  campo,
  confirmar,
  entrada,
  fmt,
  h,
  lerFormulario,
  limpar,
  mostrarErros,
  paginacao,
  PAPEIS,
  selecao,
  tabela,
} from "../ui.js";

function mostrarSenha(titulo, usuario, senha) {
  const ok = h("button", { class: "botao", type: "button", text: "Já anotei" });
  const modal = abrirDialogo({
    titulo,
    conteudo: [
      h("p", { text: `Entregue esta senha provisória para ${usuario}. Ela aparece só agora e será trocada no primeiro acesso.` }),
      h("div", { class: "senha-unica", text: senha }),
    ],
    rodape: [ok],
  });
  ok.addEventListener("click", () => modal.fechar());
}

function formularioUsuario(usuario, aoSalvar) {
  const erros = h("div", { class: "erro-form", hidden: true });
  const form = h(
    "form",
    { class: "grade-form", id: "form-usuario", novalidate: true },
    h("div", { class: "largo" }, erros),
    campo("Nome", entrada({ name: "nome", value: usuario?.nome || "", required: true }), { largo: true }),
    usuario ? null : campo("Login", entrada({ name: "usuario", required: true, autocapitalize: "none", spellcheck: "false" }), { dica: "Letras minúsculas, números, ponto ou hífen." }),
    campo("E-mail (opcional)", entrada({ type: "email", name: "email", value: usuario?.email || "" })),
    campo("Perfil", selecao(Object.entries(PAPEIS), { name: "papel", value: usuario?.papel || "vendedor" })),
    usuario ? h("label", { class: "marcador largo" }, h("input", { type: "checkbox", name: "ativo", checked: usuario.ativo }), "Acesso ativo") : null,
  );
  const salvar = h("button", { class: "botao", type: "submit", text: usuario ? "Salvar" : "Criar usuário" });
  salvar.setAttribute("form", form.id);
  const modal = abrirGaveta({
    titulo: usuario ? `Editar ${usuario.usuario}` : "Novo usuário",
    conteudo: [usuario ? null : h("p", { text: "Uma senha provisória será gerada e mostrada uma única vez." }), form],
    rodape: [salvar],
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const dados = lerFormulario(form);
    salvar.disabled = true;
    try {
      if (usuario) {
        await api.patch(`/usuarios/${usuario.id}`, dados);
        modal.fechar();
        aviso("Usuário salvo.");
      } else {
        const criado = await api.post("/usuarios", dados);
        modal.fechar();
        mostrarSenha("Usuário criado", criado.usuario.usuario, criado.senha_inicial);
      }
      aoSalvar();
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      salvar.disabled = false;
    }
  });
}

export async function usuarios(alvo, ctx) {
  const resultado = h("div");
  let paginaAtual = 1;
  async function carregar() {
    try {
      const pagina = await api.get("/usuarios", { pagina: paginaAtual, por_pagina: 50 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Nome", valor: (u) => h("span", {}, u.nome, h("span", { class: "secundaria codigo", text: u.usuario })), classe: "principal" },
            { titulo: "Perfil", valor: (u) => PAPEIS[u.papel] },
            { titulo: "Último acesso", valor: (u) => fmt.dataHora(u.ultimo_acesso) },
            { titulo: "Situação", valor: (u) => (u.ativo ? (u.trocar_senha ? h("span", { class: "selo aviso", text: "Senha provisória" }) : h("span", { class: "selo ok", text: "Ativo" })) : h("span", { class: "selo", text: "Desativado" })) },
            {
              titulo: "",
              valor: (u) =>
                h(
                  "div",
                  { class: "acoes" },
                  botao("Editar", () => formularioUsuario(u, carregar), { classe: "secundario pequeno" }),
                  botao(
                    "Nova senha",
                    async () => {
                      if (!(await confirmar({ titulo: `Gerar nova senha para ${u.usuario}?`, texto: "A senha atual deixa de funcionar e as sessões abertas são encerradas.", acao: "Gerar senha" }))) return;
                      try {
                        const r = await api.post(`/usuarios/${u.id}/redefinir-senha`);
                        mostrarSenha("Senha redefinida", u.usuario, r.senha_inicial);
                        carregar();
                      } catch (erro) {
                        avisarErro(erro);
                      }
                    },
                    { classe: "secundario pequeno" },
                  ),
                ),
            },
          ],
          linhas: pagina.itens,
        }),
        paginacao(pagina, (n) => {
          paginaAtual = n;
          carregar();
        }),
      );
    } catch (erro) {
      avisarErro(erro);
    }
  }
  alvo.append(
    cabecalhoPagina("Usuários", "Perfis: Administração faz tudo; Gerência aprova preços, compras e cancelamentos; Vendas cria pedidos; Estoque separa, fatura e recebe.", [
      botao("Novo usuário", () => formularioUsuario(null, carregar), { iconeNome: "mais" }),
    ]),
    h("section", { class: "bloco" }, resultado),
  );
  await carregar();
}

const ACOES_AUDITORIA = [
  "",
  "login",
  "login_falhou",
  "senha_trocada",
  "documento_revelado",
  "pedido_criado",
  "pedido_confirmar",
  "pedido_faturar",
  "pedido_cancelar",
  "produto_alterado",
  "estoque_ajuste",
  "estoque_transferencia",
  "compra_recebida",
  "usuario_criado",
  "usuario_alterado",
];

export async function auditoria(alvo) {
  const filtros = { acao: "", pagina: 1 };
  const resultado = h("div");
  async function carregar() {
    try {
      const pagina = await api.get("/auditoria", { ...filtros, por_pagina: 30 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Quando", valor: (a) => fmt.dataHora(a.criado_em) },
            { titulo: "Usuário", valor: (a) => h("span", { class: "codigo", text: a.usuario || "—" }) },
            { titulo: "Ação", valor: (a) => a.acao.replaceAll("_", " ") },
            { titulo: "Registro", valor: (a) => `${a.entidade}${a.entidade_id ? ` #${a.entidade_id}` : ""}` },
            { titulo: "Detalhes", valor: (a) => (a.detalhes ? h("pre", { class: "json", text: JSON.stringify(a.detalhes, null, 1) }) : "—") },
          ],
          linhas: pagina.itens,
          vazio: "Nenhum registro.",
        }),
        paginacao(pagina, (n) => {
          filtros.pagina = n;
          carregar();
        }),
      );
    } catch (erro) {
      avisarErro(erro);
    }
  }
  const acao = selecao(ACOES_AUDITORIA.map((a) => [a, a ? a.replaceAll("_", " ") : "Todas"]));
  acao.addEventListener("change", () => {
    filtros.acao = acao.value;
    filtros.pagina = 1;
    carregar();
  });
  alvo.append(
    cabecalhoPagina("Auditoria", "Quem fez o quê e quando. Endereços IP não são guardados; só um código irreversível da origem.", []),
    h("div", { class: "filtros" }, campo("Ação", acao)),
    h("section", { class: "bloco" }, resultado),
  );
  await carregar();
}
