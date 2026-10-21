import { api } from "../api.js";
import {
  abrirGaveta,
  autocompletar,
  aviso,
  avisarErro,
  bloco,
  botao,
  cabecalhoPagina,
  campo,
  confirmar,
  dinheiroParaApi,
  entrada,
  fmt,
  h,
  icone,
  limpar,
  link,
  mostrarErros,
  paginacao,
  selecao,
  selo,
  STATUS_COMPRA,
  tabela,
} from "../ui.js";

const recarregar = () => window.dispatchEvent(new HashChangeEvent("hashchange"));

export async function lista(alvo, ctx) {
  const filtros = { status: ctx.query.status || "", pagina: 1 };
  const resultado = h("div");
  async function carregar() {
    try {
      const pagina = await api.get("/compras", { status: filtros.status ? [filtros.status] : [], pagina: filtros.pagina, por_pagina: 25 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Compra", valor: (c) => h("a", { href: `#/compras/${c.id}`, class: "codigo", text: c.numero }) },
            { titulo: "Fornecedor", valor: (c) => c.fornecedor, classe: "principal" },
            { titulo: "Status", valor: (c) => selo(c.status, STATUS_COMPRA) },
            { titulo: "Depósito", valor: (c) => h("span", { class: "codigo", text: c.deposito }) },
            { titulo: "Recebido", valor: (c) => fmt.percentual(c.percentual_recebido, 0), classe: "num" },
            { titulo: "Previsão", valor: (c) => fmt.data(c.previsao_entrega) },
            { titulo: "Total", valor: (c) => fmt.moeda(c.total), classe: "num" },
          ],
          linhas: pagina.itens,
          aoClicar: (c) => ctx.navegar(`compras/${c.id}`),
          vazio: "Nenhum pedido de compra com esse filtro.",
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
  const status = selecao([["", "Todos"], ...Object.entries(STATUS_COMPRA)], { value: filtros.status });
  status.addEventListener("change", () => {
    filtros.status = status.value;
    filtros.pagina = 1;
    carregar();
  });
  alvo.append(
    cabecalhoPagina(
      "Pedidos de compra",
      "Ao receber a mercadoria, o estoque entra no depósito e o custo médio do produto é recalculado.",
      ctx.gestao() ? [link("Nova compra", "#/compras/nova")] : [],
    ),
    h("div", { class: "filtros" }, campo("Status", status)),
    h("section", { class: "bloco" }, resultado),
  );
  await carregar();
}

export async function nova(alvo, ctx) {
  const [fornecedores, depositos] = await Promise.all([api.get("/fornecedores", { ativo: true, por_pagina: 200 }), api.get("/depositos", { ativo: true })]);
  const itens = [];
  const erros = h("div", { class: "erro-form", hidden: true });
  const fornecedor = selecao(fornecedores.itens.map((f) => [f.id, f.nome_fantasia || f.razao_social]), { name: "fornecedor_id" });
  const deposito = selecao(depositos.map((d) => [d.id, `${d.codigo}, ${d.nome}`]), { name: "deposito_id" });
  const previsao = entrada({ type: "date", name: "previsao_entrega" });
  const observacoes = h("textarea", { name: "observacoes" });
  const listaItens = h("div", { class: "itens-form" });
  const total = h("strong");
  const busca = entrada({ placeholder: "Nome ou SKU do produto" });

  function desenhar() {
    const soma = itens.reduce((s, i) => s + i.quantidade * (Number(dinheiroParaApi(i.custo)) || 0), 0);
    total.textContent = fmt.moeda(soma);
    if (!itens.length) {
      limpar(listaItens, h("div", { class: "vazio" }, h("strong", { text: "Nenhum item ainda." }), h("p", { text: "Busque um produto acima." })));
      return;
    }
    limpar(
      listaItens,
      h("div", { class: "item-form cabecalho-itens", "aria-hidden": "true" }, h("span", { text: "Produto" }), h("span", { text: "Quantidade" }), h("span", { text: "Custo unit." }), h("span", { class: "valor", text: "Total" }), h("span")),
      itens.map((item, i) => {
        const qtd = entrada({ type: "number", min: 1, value: item.quantidade, "aria-label": `Quantidade de ${item.nome}` });
        const custo = entrada({ inputmode: "decimal", value: item.custo, "aria-label": `Custo unitário de ${item.nome}` });
        const valor = h("div", { class: "valor" });
        const atualizarValor = () => {
          valor.textContent = fmt.moeda(item.quantidade * (Number(dinheiroParaApi(item.custo)) || 0));
        };
        atualizarValor();
        qtd.addEventListener("input", () => {
          item.quantidade = Math.max(1, Number(qtd.value) || 1);
          atualizarValor();
          total.textContent = fmt.moeda(itens.reduce((s, x) => s + x.quantidade * (Number(dinheiroParaApi(x.custo)) || 0), 0));
        });
        custo.addEventListener("input", () => {
          item.custo = custo.value;
          atualizarValor();
          total.textContent = fmt.moeda(itens.reduce((s, x) => s + x.quantidade * (Number(dinheiroParaApi(x.custo)) || 0), 0));
        });
        const remover = h("button", { class: "icone-botao", type: "button", "aria-label": `Remover ${item.nome}`, onclick: () => (itens.splice(i, 1), desenhar()) }, icone("lixeira"));
        return h("div", { class: "item-form" }, h("div", { class: "descricao" }, h("strong", { text: item.nome }), h("span", { text: `${item.sku}, custo médio atual ${fmt.moeda(item.custoAtual)}` })), qtd, custo, valor, remover);
      }),
    );
  }

  const caixa = autocompletar(
    busca,
    async (q) => (await api.get("/produtos", { q, ativo: true, por_pagina: 8 })).itens.map((p) => ({ rotulo: p.nome, detalhe: `${p.sku}, ${fmt.numero(p.disponivel_total)} disponíveis`, valor: p })),
    ({ valor: p }) => {
      busca.value = "";
      if (!itens.some((i) => i.produto_id === p.id)) {
        itens.push({ produto_id: p.id, nome: p.nome, sku: p.sku, quantidade: Math.max(p.estoque_minimo * 2, 10), custo: String(p.custo_medio || "").replace(".", ","), custoAtual: p.custo_medio });
      }
      desenhar();
    },
  );

  const form = h("form", { id: "form-compra", novalidate: true });
  const salvar = h("button", { class: "botao", type: "submit", text: "Criar pedido de compra" });
  salvar.setAttribute("form", form.id);
  form.append(
    erros,
    h(
      "div",
      { class: "colunas" },
      bloco("Itens", h("div", { class: "pilha" }, h("label", { class: "campo" }, h("span", { text: "Adicionar produto" }), caixa), listaItens)),
      h(
        "div",
        { class: "pilha" },
        bloco("Fornecedor e destino", h("div", { class: "grade-form" }, campo("Fornecedor", fornecedor, { largo: true }), campo("Depósito de destino", deposito, { largo: true }), campo("Previsão de entrega", previsao, { largo: true }))),
        bloco("Total", total),
        bloco("Observações", observacoes),
      ),
    ),
  );
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!itens.length) return mostrarErros(erros, { message: "Adicione pelo menos um item." }, form);
    salvar.disabled = true;
    try {
      const compra = await api.post("/compras", {
        fornecedor_id: Number(fornecedor.value),
        deposito_id: Number(deposito.value),
        previsao_entrega: previsao.value || null,
        observacoes: observacoes.value.trim() || null,
        itens: itens.map((i) => ({ produto_id: i.produto_id, quantidade: i.quantidade, custo_unitario: dinheiroParaApi(i.custo) || "0" })),
      });
      aviso(`Pedido de compra ${compra.numero} criado.`);
      ctx.navegar(`compras/${compra.id}`);
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      salvar.disabled = false;
    }
  });
  desenhar();
  alvo.append(cabecalhoPagina("Nova compra", "O pedido nasce como rascunho; envie ao fornecedor quando estiver fechado.", [salvar], { href: "#/compras", texto: "Compras" }), form);
}

function abrirRecebimento(compra) {
  const pendentes = compra.itens.filter((i) => i.pendente > 0);
  const campos = pendentes.map((i) => ({ item: i, input: entrada({ type: "number", min: 0, max: i.pendente, value: i.pendente, "aria-label": `Receber ${i.produto}` }) }));
  const erros = h("div", { class: "erro-form", hidden: true });
  const form = h(
    "form",
    { id: "form-receber" },
    erros,
    tabela({
      colunas: [
        { titulo: "Produto", valor: ({ item }) => h("span", {}, item.produto, h("span", { class: "secundaria codigo", text: item.sku })) },
        { titulo: "Falta", valor: ({ item }) => fmt.numero(item.pendente), classe: "num" },
        { titulo: "Receber agora", valor: ({ input }) => input },
      ],
      linhas: campos,
    }),
  );
  const enviar = h("button", { class: "botao", type: "submit", text: "Dar entrada no estoque" });
  enviar.setAttribute("form", form.id);
  const modal = abrirGaveta({ titulo: `Receber ${compra.numero}`, conteudo: [h("p", { text: `Entrada no depósito ${compra.deposito}. Deixe 0 para o que não chegou.` }), form], rodape: [enviar] });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    enviar.disabled = true;
    try {
      await api.post(`/compras/${compra.id}/receber`, { itens: campos.map(({ item, input }) => ({ item_id: item.id, quantidade: Number(input.value) || 0 })) });
      modal.fechar();
      aviso("Recebimento registrado e estoque atualizado.");
      recarregar();
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      enviar.disabled = false;
    }
  });
}

export async function detalhe(alvo, ctx) {
  const [id] = ctx.params;
  const compra = await api.get(`/compras/${id}`);
  const acoes = [];
  if (ctx.gestao() && ["RASCUNHO", "ENVIADO"].includes(compra.status)) {
    acoes.push(
      botao("Cancelar compra", async () => {
        if (!(await confirmar({ titulo: `Cancelar ${compra.numero}?`, texto: "O pedido de compra deixa de valer.", acao: "Cancelar compra", perigo: true }))) return;
        try {
          await api.post(`/compras/${compra.id}/cancelar`);
          aviso("Pedido de compra cancelado.");
          recarregar();
        } catch (erro) {
          avisarErro(erro);
        }
      }, { classe: "secundario" }),
    );
  }
  if (ctx.gestao() && compra.status === "RASCUNHO") {
    acoes.push(
      botao("Enviar ao fornecedor", async () => {
        try {
          await api.post(`/compras/${compra.id}/enviar`);
          aviso("Pedido enviado ao fornecedor.");
          recarregar();
        } catch (erro) {
          avisarErro(erro);
        }
      }),
    );
  }
  if (ctx.pode("estoquista", "gerente") && ["ENVIADO", "RECEBIDO_PARCIAL"].includes(compra.status)) {
    acoes.push(botao("Receber mercadoria", () => abrirRecebimento(compra)));
  }

  alvo.append(
    cabecalhoPagina(compra.numero, `${compra.fornecedor}, destino ${compra.deposito}.`, acoes, { href: "#/compras", texto: "Compras" }),
  );
  alvo.querySelector(".cabecalho-pagina h1").after(h("div", { style: { marginTop: "8px" } }, selo(compra.status, STATUS_COMPRA)));
  alvo.append(
    h(
      "div",
      { class: "colunas" },
      bloco(
        "Itens",
        tabela({
          colunas: [
            { titulo: "Produto", valor: (i) => h("a", { href: `#/produtos/${i.produto_id}` }, i.produto), classe: "principal" },
            { titulo: "SKU", valor: (i) => h("span", { class: "codigo", text: i.sku }) },
            { titulo: "Pedido", valor: (i) => fmt.numero(i.quantidade), classe: "num" },
            { titulo: "Recebido", valor: (i) => fmt.numero(i.quantidade_recebida), classe: "num" },
            { titulo: "Custo", valor: (i) => fmt.moeda(i.custo_unitario), classe: "num" },
            { titulo: "Total", valor: (i) => fmt.moeda(i.total), classe: "num" },
          ],
          linhas: compra.itens,
          rodape: h("tr", {}, h("td", { colspan: 5, text: "Total" }), h("td", { class: "num", text: fmt.moeda(compra.total) })),
        }),
        { semCorpo: true },
      ),
      bloco(
        "Dados",
        h(
          "dl",
          { class: "definicoes" },
          h("dt", { text: "Criado em" }),
          h("dd", { text: `${fmt.dataHora(compra.criado_em)}${compra.criado_por ? `, por ${compra.criado_por}` : ""}` }),
          h("dt", { text: "Enviado em" }),
          h("dd", { text: fmt.dataHora(compra.enviado_em) }),
          h("dt", { text: "Previsão" }),
          h("dd", { text: fmt.data(compra.previsao_entrega) }),
          h("dt", { text: "Recebido" }),
          h("dd", { text: `${fmt.percentual(compra.percentual_recebido, 0)}${compra.recebido_em ? ` em ${fmt.dataHora(compra.recebido_em)}` : ""}` }),
          compra.observacoes ? [h("dt", { text: "Observações" }), h("dd", { text: compra.observacoes })] : null,
        ),
      ),
    ),
  );
}
