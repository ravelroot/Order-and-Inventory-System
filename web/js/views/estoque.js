import { api } from "../api.js";
import {
  abrirGaveta,
  autocompletar,
  aviso,
  avisarErro,
  botao,
  cabecalhoPagina,
  campo,
  dinheiroParaApi,
  entrada,
  fmt,
  h,
  limpar,
  mostrarErros,
  paginacao,
  selecao,
  tabela,
  TIPOS_MOV,
} from "../ui.js";

const OPERACOES = {
  entrada: {
    titulo: "Registrar entrada",
    descricao: "Mercadoria que chegou fora de um pedido de compra (amostra, devolução de cliente, bonificação).",
    rota: "/estoque/entradas",
    acao: "Registrar entrada",
    sucesso: "Entrada registrada.",
  },
  ajuste: {
    titulo: "Ajustar por contagem",
    descricao: "Informe quanto foi contado fisicamente. A diferença vira um ajuste no histórico, com o motivo.",
    rota: "/estoque/ajustes",
    acao: "Salvar contagem",
    sucesso: "Contagem registrada.",
  },
  transferencia: {
    titulo: "Transferir entre depósitos",
    descricao: "Só o saldo disponível (não reservado) pode ser transferido.",
    rota: "/estoque/transferencias",
    acao: "Transferir",
    sucesso: "Transferência registrada.",
  },
};

function abrirOperacao(tipo, depositos, produtoInicial, aoConcluir) {
  const op = OPERACOES[tipo];
  let produto = produtoInicial;
  const erros = h("div", { class: "erro-form", hidden: true });
  const busca = entrada({ placeholder: "Nome ou SKU", value: produto ? `${produto.nome} (${produto.sku})` : "" });
  const saldoInfo = h("small", { class: "mudo" });
  const opcoesDeposito = depositos.map((d) => [d.id, `${d.codigo}, ${d.nome}`]);
  const deposito = selecao(opcoesDeposito, { name: "deposito_id" });
  const destino = selecao(opcoesDeposito, { name: "deposito_destino_id", value: depositos[1]?.id });
  const quantidade = entrada({ type: "number", name: "quantidade", min: tipo === "ajuste" ? 0 : 1, step: 1, required: true });
  const custo = entrada({ name: "custo_unitario", inputmode: "decimal", placeholder: "Opcional" });
  const motivo = entrada({ name: "motivo", maxlength: 255, required: tipo === "ajuste", placeholder: tipo === "ajuste" ? "Ex.: inventário mensal, avaria" : "" });

  async function mostrarSaldo() {
    if (!produto) return;
    const saldos = await api.get(`/produtos/${produto.id}/saldos`);
    const saldo = saldos.find((s) => String(s.deposito_id) === deposito.value);
    saldoInfo.textContent = saldo
      ? `Neste depósito: ${fmt.numero(saldo.quantidade)} físico, ${fmt.numero(saldo.reservado)} reservado, ${fmt.numero(saldo.disponivel)} disponível.`
      : "Sem saldo neste depósito.";
  }
  deposito.addEventListener("change", () => mostrarSaldo().catch(() => {}));

  const caixa = autocompletar(
    busca,
    async (q) => (await api.get("/produtos", { q, por_pagina: 8 })).itens.map((p) => ({ rotulo: p.nome, detalhe: p.sku, valor: p })),
    (item) => {
      produto = item.valor;
      busca.value = `${produto.nome} (${produto.sku})`;
      mostrarSaldo().catch(() => {});
    },
  );
  mostrarSaldo().catch(() => {});

  const form = h(
    "form",
    { class: "grade-form", id: "form-estoque", novalidate: true },
    h("div", { class: "largo" }, erros),
    h("label", { class: "campo largo" }, h("span", { text: "Produto" }), caixa, saldoInfo),
    campo(tipo === "transferencia" ? "Sair de" : "Depósito", deposito),
    tipo === "transferencia" ? campo("Entrar em", destino) : null,
    campo(tipo === "ajuste" ? "Quantidade contada" : "Quantidade", quantidade),
    tipo === "entrada" ? campo("Custo unitário (R$)", custo, { dica: "Atualiza o custo médio do produto." }) : null,
    campo("Motivo", motivo, { largo: true }),
  );
  const enviar = h("button", { class: "botao", type: "submit", text: op.acao });
  enviar.setAttribute("form", form.id);
  const modal = abrirGaveta({ titulo: op.titulo, conteudo: [h("p", { text: op.descricao }), form], rodape: [enviar] });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!produto) return mostrarErros(erros, { message: "Escolha um produto." }, form);
    const base = { produto_id: produto.id };
    const qtd = Number(quantidade.value);
    let corpo;
    if (tipo === "entrada") {
      corpo = { ...base, deposito_id: Number(deposito.value), quantidade: qtd, custo_unitario: dinheiroParaApi(custo.value) };
      if (motivo.value.trim()) corpo.motivo = motivo.value.trim();
    } else if (tipo === "ajuste") {
      corpo = { ...base, deposito_id: Number(deposito.value), quantidade_contada: qtd, motivo: motivo.value.trim() };
    } else {
      corpo = { ...base, deposito_origem_id: Number(deposito.value), deposito_destino_id: Number(destino.value), quantidade: qtd };
      if (motivo.value.trim()) corpo.motivo = motivo.value.trim();
    }
    enviar.disabled = true;
    try {
      const resposta = await api.post(op.rota, corpo);
      modal.fechar();
      aviso(resposta === null ? "A contagem bate com o saldo; nada foi alterado." : op.sucesso);
      aoConcluir();
    } catch (erro) {
      if (erro.codigo === "estoque_insuficiente" && erro.detalhes?.[0]) {
        erro.message = `${erro.message} Disponível: ${erro.detalhes[0].disponivel}.`;
      }
      mostrarErros(erros, erro, form);
    } finally {
      enviar.disabled = false;
    }
  });
}

export async function render(alvo, ctx) {
  const depositos = await api.get("/depositos", { ativo: true });
  const produtoInicial = ctx.query.produto ? await api.get(`/produtos/${ctx.query.produto}`) : null;
  const filtros = { deposito_id: "", q: produtoInicial?.sku || "", abaixo_minimo: false, pagina: 1, aba: "saldos", paginaMov: 1, tipo: "" };
  const area = h("section", { class: "bloco" });
  const filtrosEl = h("div", { class: "filtros" });

  async function carregarSaldos() {
    const pagina = await api.get("/estoque/saldos", {
      deposito_id: filtros.deposito_id,
      q: filtros.q,
      abaixo_minimo: filtros.abaixo_minimo,
      pagina: filtros.pagina,
      por_pagina: 30,
    });
    limpar(
      area,
      tabela({
        colunas: [
          { titulo: "Produto", valor: (s) => h("a", { href: `#/produtos/${s.produto_id}` }, s.produto), classe: "principal" },
          { titulo: "SKU", valor: (s) => h("span", { class: "codigo", text: s.sku }) },
          { titulo: "Depósito", valor: (s) => h("span", { class: "codigo", text: s.deposito }) },
          { titulo: "Físico", valor: (s) => fmt.numero(s.quantidade), classe: "num" },
          { titulo: "Reservado", valor: (s) => fmt.numero(s.reservado), classe: "num" },
          { titulo: "Disponível", valor: (s) => h("span", { class: s.abaixo_minimo ? "negativo" : "", text: fmt.numero(s.disponivel) }), classe: "num" },
          { titulo: "Mínimo", valor: (s) => fmt.numero(s.estoque_minimo), classe: "num" },
          { titulo: "Valor a custo", valor: (s) => fmt.moeda(s.valor_estoque), classe: "num" },
        ],
        linhas: pagina.itens,
        vazio: "Nenhum saldo com esses filtros.",
      }),
      paginacao(pagina, (n) => {
        filtros.pagina = n;
        carregar();
      }),
    );
  }

  async function carregarMovimentos() {
    const pagina = await api.get("/estoque/movimentacoes", {
      deposito_id: filtros.deposito_id,
      produto_id: produtoInicial && filtros.q === produtoInicial.sku ? produtoInicial.id : "",
      tipo: filtros.tipo ? [filtros.tipo] : [],
      pagina: filtros.paginaMov,
      por_pagina: 30,
    });
    limpar(
      area,
      tabela({
        colunas: [
          { titulo: "Quando", valor: (m) => fmt.dataHora(m.criado_em) },
          { titulo: "Produto", valor: (m) => h("a", { href: `#/produtos/${m.produto_id}` }, m.produto, h("span", { class: "secundaria codigo", text: m.sku })) },
          { titulo: "Tipo", valor: (m) => TIPOS_MOV[m.tipo] || m.tipo },
          { titulo: "Depósito", valor: (m) => h("span", { class: "codigo", text: m.deposito }) },
          { titulo: "Qtd.", valor: (m) => fmt.numero(m.quantidade), classe: "num" },
          { titulo: "Saldo após", valor: (m) => fmt.numero(m.saldo_apos), classe: "num" },
          { titulo: "Motivo", valor: (m) => h("span", {}, m.motivo || "—", m.usuario ? h("span", { class: "secundaria", text: m.usuario }) : null) },
        ],
        linhas: pagina.itens,
        vazio: "Nenhuma movimentação com esses filtros.",
      }),
      paginacao(pagina, (n) => {
        filtros.paginaMov = n;
        carregar();
      }),
    );
  }

  function carregar() {
    return (filtros.aba === "saldos" ? carregarSaldos() : carregarMovimentos()).catch(avisarErro);
  }

  const abaSaldos = h("button", { type: "button", role: "tab", text: "Saldos" });
  const abaMov = h("button", { type: "button", role: "tab", text: "Movimentações" });
  const deposito = selecao([["", "Todos os depósitos"], ...depositos.map((d) => [d.id, `${d.codigo}, ${d.nome}`])]);
  const busca = entrada({ type: "search", placeholder: "Produto ou SKU", value: filtros.q });
  const baixo = h("input", { type: "checkbox" });
  const tipo = selecao([["", "Todos os tipos"], ...Object.entries(TIPOS_MOV)]);
  let espera;
  busca.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      filtros.q = busca.value.trim();
      filtros.pagina = 1;
      carregar();
    }, 300);
  });
  deposito.addEventListener("change", () => {
    filtros.deposito_id = deposito.value;
    filtros.pagina = filtros.paginaMov = 1;
    carregar();
  });
  baixo.addEventListener("change", () => {
    filtros.abaixo_minimo = baixo.checked;
    filtros.pagina = 1;
    carregar();
  });
  tipo.addEventListener("change", () => {
    filtros.tipo = tipo.value;
    filtros.paginaMov = 1;
    carregar();
  });

  function desenharFiltros() {
    abaSaldos.setAttribute("aria-selected", String(filtros.aba === "saldos"));
    abaMov.setAttribute("aria-selected", String(filtros.aba !== "saldos"));
    limpar(
      filtrosEl,
      campo("Depósito", deposito),
      filtros.aba === "saldos"
        ? [h("label", { class: "campo busca" }, h("span", { text: "Buscar" }), busca), h("label", { class: "marcador" }, baixo, "Só abaixo do mínimo")]
        : campo("Tipo", tipo),
    );
  }
  abaSaldos.addEventListener("click", () => {
    filtros.aba = "saldos";
    desenharFiltros();
    carregar();
  });
  abaMov.addEventListener("click", () => {
    filtros.aba = "movimentacoes";
    desenharFiltros();
    carregar();
  });

  const acoes = ctx.pode("estoquista", "gerente")
    ? [
        botao("Transferir", () => abrirOperacao("transferencia", depositos, produtoInicial, carregar), { classe: "secundario" }),
        botao("Ajustar por contagem", () => abrirOperacao("ajuste", depositos, produtoInicial, carregar), { classe: "secundario" }),
        botao("Registrar entrada", () => abrirOperacao("entrada", depositos, produtoInicial, carregar), { iconeNome: "mais" }),
      ]
    : [];

  desenharFiltros();
  alvo.append(
    cabecalhoPagina("Estoque", "Saldos por depósito e o histórico completo de movimentações.", acoes),
    h("div", { class: "abas", role: "tablist" }, abaSaldos, abaMov),
    filtrosEl,
    area,
  );
  await carregar();
}
