import { api } from "../api.js";
import {
  abrirGaveta,
  aviso,
  avisarErro,
  baixarArquivo,
  bloco,
  botao,
  cabecalhoPagina,
  campo,
  dinheiroParaApi,
  entrada,
  fmt,
  h,
  limpar,
  lerFormulario,
  mostrarErros,
  paginacao,
  selecao,
  tabela,
  TIPOS_MOV,
} from "../ui.js";

const UNIDADES = ["UN", "CX", "PC", "KIT", "PAR", "RL"];

async function opcoesCadastro() {
  const [categorias, fornecedores] = await Promise.all([api.get("/categorias", { ativo: true }), api.get("/fornecedores", { ativo: true, por_pagina: 200 })]);
  return { categorias, fornecedores: fornecedores.itens };
}

export async function abrirFormularioProduto(produto, aoSalvar) {
  const { categorias, fornecedores } = await opcoesCadastro();
  const erros = h("div", { class: "erro-form", hidden: true });
  const form = h(
    "form",
    { class: "grade-form", id: "form-produto", novalidate: true },
    h("div", { class: "largo" }, erros),
    campo("SKU", entrada({ name: "sku", value: produto?.sku || "", disabled: Boolean(produto), required: true, maxlength: 30 }), {
      dica: produto ? "O SKU não muda depois de criado." : "Letras, números e hífen.",
    }),
    campo("Código de barras (EAN-13)", entrada({ name: "codigo_barras", value: produto?.codigo_barras || "", inputmode: "numeric", maxlength: 14 })),
    campo("Nome", entrada({ name: "nome", value: produto?.nome || "", required: true, maxlength: 160 }), { largo: true }),
    campo("Categoria", selecao(categorias.map((c) => [c.id, c.nome]), { name: "categoria_id", value: produto?.categoria_id })),
    campo("Fornecedor principal", selecao([["", "Sem fornecedor"], ...fornecedores.map((f) => [f.id, f.nome_fantasia || f.razao_social])], { name: "fornecedor_id", value: produto?.fornecedor_id ?? "" })),
    campo("Unidade", selecao(UNIDADES, { name: "unidade", value: produto?.unidade || "UN" })),
    campo("Preço de venda (R$)", entrada({ name: "preco_venda", inputmode: "decimal", value: produto ? String(produto.preco_venda).replace(".", ",") : "", required: true })),
    campo("Estoque mínimo", entrada({ type: "number", name: "estoque_minimo", min: 0, value: produto?.estoque_minimo ?? 0 }), {
      dica: "Abaixo disso o produto entra na lista de reposição.",
    }),
    campo("Descrição", h("textarea", { name: "descricao", value: produto?.descricao || "" }), { largo: true }),
    h("label", { class: "marcador largo" }, h("input", { type: "checkbox", name: "ativo", checked: produto ? produto.ativo : true }), "Produto ativo (aparece nas vendas)"),
  );
  const salvar = h("button", { class: "botao", type: "submit", text: produto ? "Salvar produto" : "Cadastrar produto" });
  salvar.setAttribute("form", form.id);
  const modal = abrirGaveta({ titulo: produto ? `Editar ${produto.sku}` : "Novo produto", conteudo: form, rodape: [salvar] });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const dados = lerFormulario(form);
    dados.preco_venda = dinheiroParaApi(dados.preco_venda);
    dados.categoria_id = Number(dados.categoria_id);
    dados.fornecedor_id = dados.fornecedor_id ? Number(dados.fornecedor_id) : null;
    salvar.disabled = true;
    try {
      let salvo;
      if (produto) {
        delete dados.sku;
        salvo = await api.patch(`/produtos/${produto.id}`, { ...dados, versao: produto.versao });
      } else {
        salvo = await api.post("/produtos", dados);
      }
      modal.fechar();
      aviso(produto ? "Produto salvo." : `Produto ${salvo.sku} cadastrado.`);
      aoSalvar?.(salvo);
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      salvar.disabled = false;
    }
  });
}

function seloEstoque(p) {
  if (p.disponivel_total <= 0) return h("span", { class: "selo alerta", text: "Sem saldo" });
  if (p.abaixo_minimo) return h("span", { class: "selo aviso", text: "Abaixo do mínimo" });
  return null;
}

export async function lista(alvo, ctx) {
  const categorias = await api.get("/categorias");
  const filtros = { q: ctx.query.q || "", categoria_id: "", abaixo_minimo: ctx.query.abaixo_minimo === "1", ativo: "true", ordem: "nome", pagina: 1 };
  const resultado = h("div");

  const parametros = () => ({
    q: filtros.q,
    categoria_id: filtros.categoria_id,
    abaixo_minimo: filtros.abaixo_minimo,
    ativo: filtros.ativo,
  });

  async function carregar() {
    try {
      const pagina = await api.get("/produtos", { ...parametros(), ordem: filtros.ordem, pagina: filtros.pagina, por_pagina: 25 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Produto", valor: (p) => h("span", {}, p.nome, h("span", { class: "secundaria", text: p.categoria })), classe: "principal" },
            { titulo: "SKU", valor: (p) => h("span", { class: "codigo", text: p.sku }) },
            { titulo: "Preço", valor: (p) => fmt.moeda(p.preco_venda), classe: "num" },
            { titulo: "Margem", valor: (p) => fmt.percentual(p.margem_percentual), classe: "num" },
            { titulo: "Disponível", valor: (p) => fmt.numero(p.disponivel_total), classe: "num" },
            { titulo: "Reservado", valor: (p) => fmt.numero(p.reservado_total), classe: "num" },
            { titulo: "Mínimo", valor: (p) => fmt.numero(p.estoque_minimo), classe: "num" },
            { titulo: "", valor: (p) => (p.ativo ? seloEstoque(p) : h("span", { class: "selo", text: "Inativo" })) },
          ],
          linhas: pagina.itens,
          aoClicar: (p) => ctx.navegar(`produtos/${p.id}`),
          vazio: "Nenhum produto com esses filtros.",
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

  const busca = entrada({ type: "search", value: filtros.q, placeholder: "Nome, SKU ou código de barras" });
  const categoria = selecao([["", "Todas"], ...categorias.map((c) => [c.id, c.nome])]);
  const situacao = selecao([["true", "Ativos"], ["false", "Inativos"], ["", "Todos"]], { value: "true" });
  const ordem = selecao([["nome", "Nome (A–Z)"], ["-preco", "Maior preço"], ["preco", "Menor preço"], ["-atualizado", "Alterados por último"]]);
  const baixo = h("input", { type: "checkbox", checked: filtros.abaixo_minimo });
  let espera;
  busca.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      filtros.q = busca.value.trim();
      filtros.pagina = 1;
      carregar();
    }, 300);
  });
  for (const [el, chave] of [[categoria, "categoria_id"], [situacao, "ativo"], [ordem, "ordem"]]) {
    el.addEventListener("change", () => {
      filtros[chave] = el.value;
      filtros.pagina = 1;
      carregar();
    });
  }
  baixo.addEventListener("change", () => {
    filtros.abaixo_minimo = baixo.checked;
    filtros.pagina = 1;
    carregar();
  });

  const acoes = [botao("Exportar CSV", () => baixarArquivo(api.urlExportacao("/produtos/exportar", parametros())), { classe: "secundario", iconeNome: "baixar" })];
  if (ctx.gestao()) acoes.push(botao("Novo produto", () => abrirFormularioProduto(null, (p) => ctx.navegar(`produtos/${p.id}`)), { iconeNome: "mais" }));

  alvo.append(
    cabecalhoPagina("Produtos", "Saldo disponível é o estoque físico menos o que já está reservado para pedidos confirmados.", acoes),
    h(
      "div",
      { class: "filtros" },
      h("label", { class: "campo busca" }, h("span", { text: "Buscar" }), busca),
      campo("Categoria", categoria),
      campo("Situação", situacao),
      campo("Ordenar por", ordem),
      h("label", { class: "marcador" }, baixo, "Só abaixo do mínimo"),
    ),
    h("section", { class: "bloco" }, resultado),
  );
  await carregar();
}

export async function detalhe(alvo, ctx) {
  const [id] = ctx.params;
  const [produto, saldos] = await Promise.all([api.get(`/produtos/${id}`), api.get(`/produtos/${id}/saldos`)]);
  const movimentos = h("div");
  let paginaMov = 1;

  async function carregarMovimentos() {
    const pagina = await api.get(`/produtos/${id}/movimentacoes`, { pagina: paginaMov, por_pagina: 15 });
    limpar(
      movimentos,
      tabela({
        colunas: [
          { titulo: "Quando", valor: (m) => fmt.dataHora(m.criado_em) },
          { titulo: "Tipo", valor: (m) => TIPOS_MOV[m.tipo] || m.tipo },
          { titulo: "Depósito", valor: (m) => h("span", { class: "codigo", text: m.deposito }) },
          { titulo: "Qtd.", valor: (m) => fmt.numero(m.quantidade), classe: "num" },
          { titulo: "Saldo após", valor: (m) => fmt.numero(m.saldo_apos), classe: "num" },
          { titulo: "Reservado após", valor: (m) => fmt.numero(m.reservado_apos), classe: "num" },
          { titulo: "Motivo", valor: (m) => h("span", {}, m.motivo || "—", m.usuario ? h("span", { class: "secundaria", text: m.usuario }) : null) },
        ],
        linhas: pagina.itens,
        vazio: "Nenhuma movimentação ainda.",
      }),
      paginacao(pagina, (n) => {
        paginaMov = n;
        carregarMovimentos().catch(avisarErro);
      }),
    );
  }
  await carregarMovimentos();

  const acoes = [];
  if (ctx.gestao()) acoes.push(botao("Editar", () => abrirFormularioProduto(produto, () => window.dispatchEvent(new HashChangeEvent("hashchange"))), { classe: "secundario" }));
  if (ctx.pode("estoquista", "gerente")) acoes.push(botao("Movimentar estoque", () => ctx.navegar(`estoque?produto=${produto.id}`)));

  const dados = h(
    "dl",
    { class: "definicoes" },
    h("dt", { text: "SKU" }),
    h("dd", { class: "codigo", text: produto.sku }),
    h("dt", { text: "Código de barras" }),
    h("dd", { class: "codigo", text: produto.codigo_barras || "—" }),
    h("dt", { text: "Categoria" }),
    h("dd", { text: produto.categoria }),
    h("dt", { text: "Fornecedor" }),
    h("dd", { text: produto.fornecedor || "—" }),
    h("dt", { text: "Unidade" }),
    h("dd", { text: produto.unidade }),
    h("dt", { text: "Preço de venda" }),
    h("dd", { text: fmt.moeda(produto.preco_venda) }),
    h("dt", { text: "Custo médio" }),
    h("dd", { text: fmt.moeda(produto.custo_medio) }),
    h("dt", { text: "Margem" }),
    h("dd", { text: fmt.percentual(produto.margem_percentual) }),
    h("dt", { text: "Estoque mínimo" }),
    h("dd", { text: fmt.numero(produto.estoque_minimo) }),
  );

  const tabelaSaldos = tabela({
    colunas: [
      { titulo: "Depósito", valor: (s) => h("span", { class: "codigo", text: s.deposito }) },
      { titulo: "Físico", valor: (s) => fmt.numero(s.quantidade), classe: "num" },
      { titulo: "Reservado", valor: (s) => fmt.numero(s.reservado), classe: "num" },
      { titulo: "Disponível", valor: (s) => fmt.numero(s.disponivel), classe: "num" },
      { titulo: "Valor a custo", valor: (s) => fmt.moeda(s.valor_estoque), classe: "num" },
    ],
    linhas: saldos,
    vazio: "Ainda sem estoque em nenhum depósito.",
    rodape: saldos.length
      ? h(
          "tr",
          {},
          h("td", { text: "Total" }),
          h("td", { class: "num", text: fmt.numero(produto.estoque_total) }),
          h("td", { class: "num", text: fmt.numero(produto.reservado_total) }),
          h("td", { class: "num", text: fmt.numero(produto.disponivel_total) }),
          h("td", { class: "num", text: fmt.moeda(saldos.reduce((s, x) => s + x.valor_estoque, 0)) }),
        )
      : null,
  });

  alvo.append(
    cabecalhoPagina(produto.nome, produto.descricao, acoes, { href: "#/produtos", texto: "Produtos" }),
    h(
      "div",
      { class: "colunas" },
      h("div", { class: "pilha" }, bloco("Saldo por depósito", tabelaSaldos, { semCorpo: true }), bloco("Movimentações", movimentos, { descricao: "Registro imutável de tudo que alterou o saldo.", semCorpo: true })),
      bloco("Cadastro", dados),
    ),
  );
}
