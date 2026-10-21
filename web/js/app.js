import { api } from "./api.js";
import { abrirDialogo, aviso, avisarErro, campo, entrada, h, icone, limpar, mostrarErros, PAPEIS } from "./ui.js";
import * as painel from "./views/painel.js";
import * as pedidos from "./views/pedidos.js";
import * as produtos from "./views/produtos.js";
import * as estoque from "./views/estoque.js";
import * as compras from "./views/compras.js";
import * as clientes from "./views/clientes.js";
import * as fornecedores from "./views/fornecedores.js";
import * as relatorios from "./views/relatorios.js";
import * as administracao from "./views/administracao.js";

const TODOS = ["admin", "gerente", "vendedor", "estoquista"];
const GESTAO = ["admin", "gerente"];

const MENU = [
  { grupo: null, itens: [{ rota: "painel", texto: "Painel", icone: "painel", papeis: TODOS }] },
  {
    grupo: "Operação",
    itens: [
      { rota: "pedidos", texto: "Pedidos", icone: "pedidos", papeis: TODOS },
      { rota: "estoque", texto: "Estoque", icone: "estoque", papeis: TODOS },
      { rota: "compras", texto: "Compras", icone: "compras", papeis: TODOS },
    ],
  },
  {
    grupo: "Cadastros",
    itens: [
      { rota: "produtos", texto: "Produtos", icone: "produtos", papeis: TODOS },
      { rota: "clientes", texto: "Clientes", icone: "clientes", papeis: TODOS },
      { rota: "fornecedores", texto: "Fornecedores", icone: "fornecedores", papeis: TODOS },
    ],
  },
  {
    grupo: "Gestão",
    itens: [
      { rota: "relatorios", texto: "Relatórios", icone: "relatorios", papeis: TODOS },
      { rota: "usuarios", texto: "Usuários", icone: "usuarios", papeis: ["admin"] },
      { rota: "auditoria", texto: "Auditoria", icone: "auditoria", papeis: ["admin"] },
    ],
  },
];

const ROTAS = [
  [/^painel$/, painel.render],
  [/^pedidos$/, pedidos.lista],
  [/^pedidos\/novo$/, pedidos.novo],
  [/^pedidos\/(\d+)$/, pedidos.detalhe],
  [/^produtos$/, produtos.lista],
  [/^produtos\/(\d+)$/, produtos.detalhe],
  [/^estoque$/, estoque.render],
  [/^compras$/, compras.lista],
  [/^compras\/nova$/, compras.nova],
  [/^compras\/(\d+)$/, compras.detalhe],
  [/^clientes$/, clientes.lista],
  [/^clientes\/(\d+)$/, clientes.detalhe],
  [/^fornecedores$/, fornecedores.lista],
  [/^relatorios$/, relatorios.render],
  [/^usuarios$/, administracao.usuarios, ["admin"]],
  [/^auditoria$/, administracao.auditoria, ["admin"]],
];

const estado = { usuario: null, versao: 0 };

export const contexto = {
  get usuario() {
    return estado.usuario;
  },
  pode: (...papeis) => estado.usuario && (estado.usuario.papel === "admin" || papeis.includes(estado.usuario.papel)),
  gestao: () => GESTAO.includes(estado.usuario?.papel),
  navegar: (rota) => {
    window.location.hash = `#/${rota}`;
  },
};

function lerRota() {
  const bruto = window.location.hash.replace(/^#\/?/, "") || "painel";
  const [caminho, busca = ""] = bruto.split("?");
  return { caminho, query: Object.fromEntries(new URLSearchParams(busca)) };
}

function aplicarTema(tema) {
  document.documentElement.dataset.tema = tema;
  try {
    localStorage.setItem("doca.tema", tema);
  } catch {
  }
}

function temaInicial() {
  try {
    const salvo = localStorage.getItem("doca.tema");
    if (salvo) return salvo;
  } catch {
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
}

function marca() {
  return h(
    "a",
    { class: "marca", href: "#/painel" },
    h("img", { src: "/static/img/icone.svg", alt: "", width: 34, height: 34 }),
    h("span", {}, h("strong", { text: "Doca" }), h("small", { text: "Pedidos e estoque" })),
  );
}

function montarLateral() {
  const lateral = document.getElementById("lateral");
  const papel = estado.usuario.papel;
  const nav = h("nav", { class: "nav", "aria-label": "Principal" });
  for (const secao of MENU) {
    const visiveis = secao.itens.filter((i) => i.papeis.includes(papel));
    if (!visiveis.length) continue;
    if (secao.grupo) nav.append(h("div", { class: "nav-grupo", text: secao.grupo }));
    for (const item of visiveis) {
      nav.append(h("a", { href: `#/${item.rota}`, dataset: { rota: item.rota } }, icone(item.icone), item.texto));
    }
  }
  const botaoTema = h("button", { class: "icone-botao", type: "button", "aria-label": "Alternar tema claro/escuro", title: "Tema" });
  const desenharTema = () => limpar(botaoTema, icone(document.documentElement.dataset.tema === "escuro" ? "sol" : "lua"));
  desenharTema();
  botaoTema.addEventListener("click", () => {
    aplicarTema(document.documentElement.dataset.tema === "escuro" ? "claro" : "escuro");
    desenharTema();
  });
  const botaoSenha = h("button", { class: "icone-botao", type: "button", "aria-label": "Trocar senha", title: "Trocar senha", onclick: () => trocarSenha(false) }, icone("chave"));
  const botaoSair = h("button", { class: "icone-botao", type: "button", "aria-label": "Sair", title: "Sair", onclick: () => api.sair() }, icone("sair"));
  limpar(
    lateral,
    marca(),
    nav,
    h(
      "div",
      { class: "lateral-rodape" },
      h("div", { class: "usuario-atual" }, h("strong", { text: estado.usuario.nome }), h("span", { text: `${PAPEIS[papel]}, login ${estado.usuario.usuario}` })),
      h("div", { class: "lateral-acoes" }, botaoTema, botaoSenha, botaoSair),
    ),
  );
  nav.addEventListener("click", () => lateral.classList.remove("aberta"));
}

function marcarMenu(caminho) {
  const raiz = caminho.split("/")[0];
  document.querySelectorAll(".nav a").forEach((a) => {
    if (a.dataset.rota === raiz) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
}

async function renderizar() {
  const { caminho, query } = lerRota();
  const alvo = document.getElementById("conteudo");
  marcarMenu(caminho);
  const versao = ++estado.versao;
  for (const [padrao, view, papeis] of ROTAS) {
    const achou = caminho.match(padrao);
    if (!achou) continue;
    if (papeis && !papeis.includes(estado.usuario.papel)) {
      limpar(alvo, h("div", { class: "pagina" }, h("div", { class: "vazio" }, h("strong", { text: "Seu perfil não acessa esta área." }), h("a", { href: "#/painel", text: "Voltar ao painel" }))));
      return;
    }
    limpar(alvo, h("div", { class: "carregando", text: "Carregando…" }));
    try {
      const pagina = h("div", { class: "pagina" });
      await view(pagina, { params: achou.slice(1), query, ...contexto, versaoAtual: () => versao === estado.versao });
      if (versao === estado.versao) {
        limpar(alvo, pagina);
        alvo.focus({ preventScroll: true });
        window.scrollTo(0, 0);
      }
    } catch (erro) {
      if (versao !== estado.versao || erro.status === 401) return;
      limpar(
        alvo,
        h(
          "div",
          { class: "pagina" },
          h("div", { class: "vazio" }, h("strong", { text: erro.status === 403 ? "Seu perfil não acessa esta área." : "Não foi possível abrir esta página." }), h("p", { text: erro.message })),
        ),
      );
    }
    return;
  }
  limpar(alvo, h("div", { class: "pagina" }, h("div", { class: "vazio" }, h("strong", { text: "Página não encontrada." }), h("a", { href: "#/painel", text: "Ir para o painel" }))));
}

function trocarSenha(obrigatorio) {
  const atual = entrada({ type: "password", name: "senha_atual", autocomplete: "current-password", required: true });
  const nova = entrada({ type: "password", name: "nova_senha", autocomplete: "new-password", minlength: 10, required: true });
  const repetir = entrada({ type: "password", name: "repetir", autocomplete: "new-password", required: true });
  const erros = h("div", { class: "erro-form", hidden: true });
  const form = h(
    "form",
    { class: "grade-form" },
    h("div", { class: "largo" }, erros),
    campo("Senha atual", atual, { largo: true }),
    campo("Nova senha", nova, { largo: true, dica: "Pelo menos 10 caracteres, com letras e números." }),
    campo("Repita a nova senha", repetir, { largo: true }),
  );
  const salvar = h("button", { class: "botao", type: "submit", text: "Trocar senha" });
  salvar.setAttribute("form", "form-senha");
  form.id = "form-senha";
  const modal = abrirDialogo({
    titulo: obrigatorio ? "Defina uma senha nova" : "Trocar senha",
    conteudo: [obrigatorio ? h("p", { text: "Sua senha é provisória. Crie uma senha pessoal para continuar." }) : null, form],
    rodape: [salvar],
    aoFechar: () => {
      if (obrigatorio && estado.usuario.trocar_senha) setTimeout(() => trocarSenha(true), 0);
    },
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (nova.value !== repetir.value) {
      mostrarErros(erros, { message: "As duas senhas novas não são iguais." }, form);
      return;
    }
    salvar.disabled = true;
    try {
      const resposta = await api.post("/auth/trocar-senha", { senha_atual: atual.value, nova_senha: nova.value });
      estado.usuario = resposta.usuario;
      modal.fechar();
      aviso("Senha trocada. As outras sessões foram encerradas.");
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      salvar.disabled = false;
    }
  });
}

async function iniciar() {
  aplicarTema(temaInicial());
  try {
    estado.usuario = await api.get("/auth/eu");
  } catch (erro) {
    if (erro.status !== 401) avisarErro(erro);
    return;
  }
  document.getElementById("estrutura").hidden = false;
  montarLateral();
  const lateral = document.getElementById("lateral");
  document.getElementById("abrir-menu").addEventListener("click", () => lateral.classList.toggle("aberta"));
  window.addEventListener("hashchange", renderizar);
  await renderizar();
  if (estado.usuario.trocar_senha) trocarSenha(true);
}

iniciar();
