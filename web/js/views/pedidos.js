import { api } from "../api.js";
import {
  abrirDialogo,
  autocompletar,
  aviso,
  avisarErro,
  baixarArquivo,
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
  STATUS_PEDIDO,
  tabela,
} from "../ui.js";

const ROTULO_ACAO = {
  confirmar: "Confirmar e reservar",
  separar: "Marcar como separado",
  faturar: "Faturar",
  enviar: "Registrar envio",
  entregar: "Confirmar entrega",
  cancelar: "Cancelar pedido",
  editar: "Editar",
};

const SUCESSO_ACAO = {
  confirmar: "Pedido confirmado e estoque reservado.",
  separar: "Pedido marcado como separado.",
  faturar: "Pedido faturado e estoque baixado.",
  enviar: "Envio registrado.",
  entregar: "Entrega confirmada.",
  cancelar: "Pedido cancelado.",
};

export async function lista(alvo, ctx) {
  const filtros = {
    q: ctx.query.q || "",
    status: ctx.query.status ? ctx.query.status.split(",") : [],
    inicio: ctx.query.inicio || "",
    fim: ctx.query.fim || "",
    meus: ctx.query.meus === "1",
    pagina: Number(ctx.query.pagina) || 1,
  };
  const resultado = h("div");
  const fichas = h("div", { class: "fichas", role: "group", "aria-label": "Filtrar por status" });

  const desenharFichas = () => {
    limpar(
      fichas,
      [["", "Todos"], ...Object.entries(STATUS_PEDIDO)].map(([valor, rotulo]) => {
        const ativo = valor ? filtros.status.includes(valor) : filtros.status.length === 0;
        return h("button", {
          class: `ficha ${valor ? `st-${valor}` : ""}`,
          type: "button",
          "aria-pressed": String(ativo),
          text: rotulo,
          onclick: () => {
            if (!valor) filtros.status = [];
            else filtros.status = ativo ? filtros.status.filter((s) => s !== valor) : [...filtros.status, valor];
            filtros.pagina = 1;
            desenharFichas();
            carregar();
          },
        });
      }),
    );
  };

  const parametros = () => ({
    q: filtros.q,
    status: filtros.status,
    inicio: filtros.inicio,
    fim: filtros.fim,
    meus: filtros.meus,
  });

  async function carregar() {
    try {
      const pagina = await api.get("/pedidos", { ...parametros(), pagina: filtros.pagina, por_pagina: 25 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Pedido", valor: (p) => h("a", { href: `#/pedidos/${p.id}`, class: "codigo", text: p.numero }) },
            { titulo: "Cliente", valor: (p) => p.cliente, classe: "principal" },
            { titulo: "Status", valor: (p) => selo(p.status) },
            { titulo: "Vendedor", valor: (p) => p.vendedor || "—" },
            { titulo: "Depósito", valor: (p) => h("span", { class: "codigo", text: p.deposito }) },
            { titulo: "Itens", valor: (p) => fmt.numero(p.quantidade_itens), classe: "num" },
            { titulo: "Criado em", valor: (p) => fmt.dataHora(p.criado_em) },
            { titulo: "Total", valor: (p) => fmt.moeda(p.total), classe: "num" },
          ],
          linhas: pagina.itens,
          aoClicar: (p) => ctx.navegar(`pedidos/${p.id}`),
          vazio: h("div", {}, h("strong", { text: "Nenhum pedido com esses filtros." }), h("p", { text: "Limpe a busca ou escolha outro status." })),
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

  const busca = entrada({ type: "search", value: filtros.q, placeholder: "Número do pedido ou cliente" });
  const inicio = entrada({ type: "date", value: filtros.inicio });
  const fim = entrada({ type: "date", value: filtros.fim });
  const meus = h("input", { type: "checkbox", checked: filtros.meus });
  let espera;
  busca.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      filtros.q = busca.value.trim();
      filtros.pagina = 1;
      carregar();
    }, 300);
  });
  for (const [el, chave] of [[inicio, "inicio"], [fim, "fim"]]) {
    el.addEventListener("change", () => {
      filtros[chave] = el.value;
      filtros.pagina = 1;
      carregar();
    });
  }
  meus.addEventListener("change", () => {
    filtros.meus = meus.checked;
    filtros.pagina = 1;
    carregar();
  });

  const acoes = [botao("Exportar CSV", () => baixarArquivo(api.urlExportacao("/pedidos/exportar", parametros())), { classe: "secundario", iconeNome: "baixar" })];
  if (ctx.pode("gerente", "vendedor")) acoes.push(link("Novo pedido", "#/pedidos/novo"));

  desenharFichas();
  alvo.append(
    cabecalhoPagina("Pedidos de venda", "Do rascunho à entrega. Confirmar um pedido reserva o estoque no depósito escolhido.", acoes),
    fichas,
    h(
      "div",
      { class: "filtros" },
      campo("Buscar", busca, {}),
      campo("Criados de", inicio),
      campo("até", fim),
      ctx.pode("vendedor", "gerente") ? h("label", { class: "marcador" }, meus, "Só os meus") : null,
    ),
    h("section", { class: "bloco" }, resultado),
  );
  alvo.querySelector(".filtros .campo").classList.add("busca");
  await carregar();
}

function acaoNaApi(pedido, acao, corpo) {
  return api.post(`/pedidos/${pedido.id}/${acao}`, corpo);
}

function pedirTexto({ titulo, texto, rotulo, acao, minimo = 1, perigo = false, nome }) {
  return new Promise((resolver) => {
    let valor = null;
    const campoTexto = entrada({ name: nome, minlength: minimo, required: true });
    const erros = h("div", { class: "erro-form", hidden: true });
    const enviar = h("button", { class: `botao ${perigo ? "perigo" : ""}`, type: "submit", text: acao });
    const form = h("form", { id: `form-${nome}`, novalidate: true }, erros, campo(rotulo, campoTexto, { largo: true }));
    enviar.setAttribute("form", form.id);
    const modal = abrirDialogo({ titulo, conteudo: [h("p", { text: texto }), form], rodape: [enviar], aoFechar: () => resolver(valor) });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (campoTexto.value.trim().length < minimo) {
        mostrarErros(erros, { message: `Escreva pelo menos ${minimo} caracteres.` }, form);
        return;
      }
      valor = campoTexto.value.trim();
      modal.fechar();
    });
  });
}

async function executarAcao(pedido, acao, ctx, recarregar) {
  if (acao === "editar") return ctx.navegar(`pedidos/novo?editar=${pedido.id}`);
  let corpo;
  if (acao === "enviar") {
    const codigo = await pedirTexto({
      titulo: "Registrar envio",
      texto: "Informe o código de rastreio da transportadora.",
      rotulo: "Código de rastreio",
      acao: "Registrar envio",
      minimo: 4,
      nome: "codigo_rastreio",
    });
    if (!codigo) return;
    corpo = { codigo_rastreio: codigo };
  } else if (acao === "cancelar") {
    const efeito =
      pedido.status === "FATURADO"
        ? "As mercadorias voltam ao estoque como estorno."
        : ["CONFIRMADO", "SEPARADO"].includes(pedido.status)
          ? "A reserva de estoque será liberada."
          : "O rascunho deixa de valer.";
    const motivo = await pedirTexto({
      titulo: `Cancelar ${pedido.numero}`,
      texto: `${efeito} Esta ação não pode ser desfeita.`,
      rotulo: "Motivo do cancelamento",
      acao: "Cancelar pedido",
      minimo: 5,
      perigo: true,
      nome: "motivo",
    });
    if (!motivo) return;
    corpo = { motivo };
  } else if (acao === "faturar") {
    const ok = await confirmar({
      titulo: `Faturar ${pedido.numero}?`,
      texto: `${fmt.numero(pedido.quantidade_itens)} unidade(s) saem do estoque de ${pedido.deposito}. Total de ${fmt.moeda(pedido.total)}.`,
      acao: "Faturar",
    });
    if (!ok) return;
  }
  try {
    await acaoNaApi(pedido, acao, corpo);
    aviso(SUCESSO_ACAO[acao]);
    recarregar();
  } catch (erro) {
    if (erro.codigo === "estoque_insuficiente" && Array.isArray(erro.detalhes)) {
      abrirDialogo({
        titulo: "Estoque insuficiente",
        conteudo: [
          h("p", { text: "Nada foi reservado. Ajuste as quantidades, troque o depósito ou registre uma entrada." }),
          tabela({
            colunas: [
              { titulo: "Produto", valor: (d) => h("span", {}, d.produto, h("span", { class: "secundaria codigo", text: d.sku })) },
              { titulo: "Pedido", valor: (d) => fmt.numero(d.solicitado), classe: "num" },
              { titulo: "Disponível", valor: (d) => fmt.numero(d.disponivel), classe: "num" },
            ],
            linhas: erro.detalhes,
          }),
        ],
      });
    } else {
      avisarErro(erro);
    }
  }
}

export async function detalhe(alvo, ctx) {
  const [id] = ctx.params;
  const pedido = await api.get(`/pedidos/${id}`);
  const recarregar = () => window.dispatchEvent(new HashChangeEvent("hashchange"));

  const botoes = pedido.acoes_disponiveis.map((acao) =>
    botao(ROTULO_ACAO[acao], () => executarAcao(pedido, acao, ctx, recarregar), {
      classe: acao === "cancelar" ? "secundario" : acao === "editar" ? "secundario" : "",
    }),
  );
  const principal = botoes.filter((b) => !b.classList.contains("secundario"));
  const secundarios = botoes.filter((b) => b.classList.contains("secundario"));

  const itens = tabela({
    colunas: [
      { titulo: "Produto", valor: (i) => h("a", { href: `#/produtos/${i.produto_id}` }, i.produto), classe: "principal" },
      { titulo: "SKU", valor: (i) => h("span", { class: "codigo", text: i.sku }) },
      { titulo: "Qtd.", valor: (i) => fmt.numero(i.quantidade), classe: "num" },
      { titulo: "Preço", valor: (i) => fmt.moeda(i.preco_unitario), classe: "num" },
      { titulo: "Desconto", valor: (i) => (i.desconto_percentual ? fmt.percentual(i.desconto_percentual, 2) : "—"), classe: "num" },
      { titulo: "Total", valor: (i) => fmt.moeda(i.total), classe: "num" },
    ],
    linhas: pedido.itens,
  });

  const totais = h(
    "dl",
    { class: "totais" },
    h("dt", { text: "Produtos" }),
    h("dd", { text: fmt.moeda(pedido.subtotal) }),
    h("dt", { text: "Descontos" }),
    h("dd", { text: pedido.desconto_total ? `− ${fmt.moeda(pedido.desconto_total)}` : "—" }),
    h("dt", { text: "Frete" }),
    h("dd", { text: fmt.moeda(pedido.frete) }),
    h("dt", { class: "total", text: "Total" }),
    h("dd", { class: "total", text: fmt.moeda(pedido.total) }),
  );

  const historico = h(
    "ol",
    { class: "linha-tempo" },
    [...pedido.historico].reverse().map((ev) =>
      h(
        "li",
        { class: `st-${ev.para_status}` },
        h("strong", { text: STATUS_PEDIDO[ev.para_status] }),
        ev.observacao ? h("div", { class: "mudo", text: ev.observacao }) : null,
        h("time", { datetime: ev.criado_em, text: `${fmt.dataHora(ev.criado_em)}${ev.usuario ? `, por ${ev.usuario}` : ""}` }),
      ),
    ),
  );

  const dados = h(
    "dl",
    { class: "definicoes" },
    h("dt", { text: "Cliente" }),
    h("dd", {}, h("a", { href: `#/clientes/${pedido.cliente_id}`, text: pedido.cliente })),
    h("dt", { text: "Depósito" }),
    h("dd", { class: "codigo", text: pedido.deposito }),
    h("dt", { text: "Vendedor" }),
    h("dd", { text: pedido.vendedor || "—" }),
    pedido.codigo_rastreio ? [h("dt", { text: "Rastreio" }), h("dd", { class: "codigo", text: pedido.codigo_rastreio })] : null,
    pedido.motivo_cancelamento ? [h("dt", { text: "Cancelamento" }), h("dd", { text: pedido.motivo_cancelamento })] : null,
    pedido.observacoes ? [h("dt", { text: "Observações" }), h("dd", { text: pedido.observacoes })] : null,
  );

  alvo.append(
    cabecalhoPagina(pedido.numero, null, [...secundarios, ...principal], { href: "#/pedidos", texto: "Pedidos" }),
  );
  alvo.querySelector(".cabecalho-pagina h1").after(h("div", { style: { marginTop: "8px" } }, selo(pedido.status)));
  alvo.append(
    h(
      "div",
      { class: "colunas" },
      h("div", { class: "pilha" }, bloco("Itens", itens, { semCorpo: true }), bloco(null, totais)),
      h("div", { class: "pilha" }, bloco("Dados do pedido", dados), bloco("Histórico", historico)),
    ),
  );
}

export async function novo(alvo, ctx) {
  const idEdicao = ctx.query.editar ? Number(ctx.query.editar) : null;
  const [depositos, existente] = await Promise.all([
    api.get("/depositos", { ativo: true }),
    idEdicao ? api.get(`/pedidos/${idEdicao}`) : Promise.resolve(null),
  ]);
  const chaveIdempotencia = crypto.randomUUID();
  const estado = {
    cliente: existente ? { id: existente.cliente_id, nome: existente.cliente } : null,
    itens: existente
      ? existente.itens.map((i) => ({
          produto_id: i.produto_id,
          nome: i.produto,
          sku: i.sku,
          preco: i.preco_unitario,
          quantidade: i.quantidade,
          desconto: i.desconto_percentual,
          disponivel: null,
        }))
      : [],
  };
  const limiteDesconto = ctx.usuario.papel === "admin" ? 100 : ctx.usuario.papel === "gerente" ? 30 : 10;

  const erros = h("div", { class: "erro-form", hidden: true });
  const deposito = selecao(depositos.map((d) => [d.id, `${d.codigo} (${d.cidade || d.nome})`]), { name: "deposito_id", value: existente?.deposito_id ?? depositos[0]?.id });
  const frete = entrada({ name: "frete", inputmode: "decimal", value: existente ? String(existente.frete).replace(".", ",") : "0,00" });
  const observacoes = h("textarea", { name: "observacoes", maxlength: 2000, value: existente?.observacoes || "" });
  const clienteBusca = entrada({ placeholder: "Nome, cidade ou documento do cliente", value: estado.cliente?.nome || "" });
  const clienteEscolhido = h("small", { class: "mudo", text: estado.cliente ? "Cliente selecionado." : "Digite para buscar." });
  const produtoBusca = entrada({ placeholder: "Nome, SKU ou código de barras" });
  const listaItens = h("div", { class: "itens-form" });
  const resumo = h("dl", { class: "totais" });

  async function consultarDisponivel(item) {
    try {
      const saldos = await api.get(`/produtos/${item.produto_id}/saldos`);
      const saldo = saldos.find((s) => String(s.deposito_id) === deposito.value);
      item.disponivel = saldo ? saldo.disponivel : 0;
    } catch {
      item.disponivel = null;
    }
    desenharItens();
  }

  const totalItem = (i) => Math.round(i.preco * i.quantidade * (100 - (i.desconto || 0))) / 100;

  function desenharResumo() {
    const bruto = estado.itens.reduce((s, i) => s + i.preco * i.quantidade, 0);
    const liquido = estado.itens.reduce((s, i) => s + totalItem(i), 0);
    const valorFrete = Number(dinheiroParaApi(frete.value)) || 0;
    limpar(
      resumo,
      h("dt", { text: "Produtos" }),
      h("dd", { text: fmt.moeda(bruto) }),
      h("dt", { text: "Descontos" }),
      h("dd", { text: bruto - liquido > 0 ? `− ${fmt.moeda(bruto - liquido)}` : "—" }),
      h("dt", { text: "Frete" }),
      h("dd", { text: fmt.moeda(valorFrete) }),
      h("dt", { class: "total", text: "Total" }),
      h("dd", { class: "total", text: fmt.moeda(liquido + valorFrete) }),
    );
  }

  function desenharItens() {
    if (!estado.itens.length) {
      limpar(listaItens, h("div", { class: "vazio" }, h("strong", { text: "Nenhum item ainda." }), h("p", { text: "Busque um produto acima para adicionar." })));
      desenharResumo();
      return;
    }
    limpar(
      listaItens,
      h("div", { class: "item-form cabecalho-itens", "aria-hidden": "true" }, h("span", { text: "Produto" }), h("span", { text: "Quantidade" }), h("span", { text: "Desconto %" }), h("span", { class: "valor", text: "Total" }), h("span")),
      estado.itens.map((item, indice) => {
        const qtd = entrada({ type: "number", min: 1, step: 1, value: item.quantidade, "aria-label": `Quantidade de ${item.nome}` });
        const desc = entrada({ type: "number", min: 0, max: limiteDesconto, step: 0.5, value: item.desconto, "aria-label": `Desconto (%) de ${item.nome}` });
        const valor = h("div", { class: "valor", text: fmt.moeda(totalItem(item)) });
        const faltando = item.disponivel !== null && item.quantidade > item.disponivel;
        const info = h(
          "span",
          { class: faltando ? "negativo" : "" },
          `${item.sku}, ${fmt.moeda(item.preco)} cada, `,
          item.disponivel === null ? "consultando saldo…" : `${fmt.numero(item.disponivel)} disponível(is) no depósito`,
        );
        qtd.addEventListener("input", () => {
          item.quantidade = Math.max(1, Number(qtd.value) || 1);
          valor.textContent = fmt.moeda(totalItem(item));
          info.classList.toggle("negativo", item.disponivel !== null && item.quantidade > item.disponivel);
          desenharResumo();
        });
        desc.addEventListener("change", () => {
          desc.value = item.desconto;
        });
        desc.addEventListener("input", () => {
          item.desconto = Math.min(limiteDesconto, Math.max(0, Number(desc.value) || 0));
          valor.textContent = fmt.moeda(totalItem(item));
          desenharResumo();
        });
        const remover = h("button", { class: "icone-botao", type: "button", "aria-label": `Remover ${item.nome}` }, icone("lixeira"));
        remover.addEventListener("click", () => {
          estado.itens.splice(indice, 1);
          desenharItens();
        });
        return h("div", { class: "item-form" }, h("div", { class: "descricao" }, h("strong", { text: item.nome }), info), qtd, desc, valor, remover);
      }),
    );
    desenharResumo();
  }

  frete.addEventListener("input", desenharResumo);
  deposito.addEventListener("change", () => estado.itens.forEach(consultarDisponivel));

  const caixaCliente = autocompletar(
    clienteBusca,
    async (q) => (await api.get("/clientes", { q, ativo: true, por_pagina: 8 })).itens.map((c) => ({ rotulo: c.nome, detalhe: [c.cidade, c.uf].filter(Boolean).join("/"), valor: c })),
    (item) => {
      estado.cliente = { id: item.valor.id, nome: item.valor.nome };
      clienteBusca.value = item.valor.nome;
      clienteEscolhido.textContent = `Documento ${item.valor.documento}${item.valor.cidade ? `, ${item.valor.cidade}/${item.valor.uf}` : ""}`;
    },
  );
  const caixaProduto = autocompletar(
    produtoBusca,
    async (q) =>
      (await api.get("/produtos", { q, ativo: true, por_pagina: 8 })).itens.map((p) => ({
        rotulo: p.nome,
        detalhe: `${p.sku}, ${fmt.moeda(p.preco_venda)}, ${fmt.numero(p.disponivel_total)} disponíveis`,
        valor: p,
      })),
    (item) => {
      const p = item.valor;
      produtoBusca.value = "";
      const existenteItem = estado.itens.find((i) => i.produto_id === p.id);
      if (existenteItem) existenteItem.quantidade += 1;
      else {
        const novoItem = { produto_id: p.id, nome: p.nome, sku: p.sku, preco: p.preco_venda, quantidade: 1, desconto: 0, disponivel: null };
        estado.itens.push(novoItem);
        consultarDisponivel(novoItem);
      }
      desenharItens();
      produtoBusca.focus();
    },
  );
  estado.itens.forEach(consultarDisponivel);

  const form = h("form", { id: "form-pedido", novalidate: true });
  const salvar = h("button", { class: "botao", type: "submit", text: idEdicao ? "Salvar alterações" : "Criar pedido" });
  salvar.setAttribute("form", form.id);
  const salvarConfirmar = idEdicao ? null : h("button", { class: "botao secundario", type: "button", text: "Criar e confirmar" });

  async function enviar(confirmarDepois) {
    mostrarErros(erros, null, form);
    if (!estado.cliente) return mostrarErros(erros, { message: "Escolha um cliente." }, form);
    if (!estado.itens.length) return mostrarErros(erros, { message: "Adicione pelo menos um item." }, form);
    const itens = estado.itens.map((i) => ({ produto_id: i.produto_id, quantidade: i.quantidade, desconto_percentual: i.desconto || 0 }));
    const corpo = {
      cliente_id: estado.cliente.id,
      deposito_id: Number(deposito.value),
      frete: dinheiroParaApi(frete.value) || "0",
      observacoes: observacoes.value.trim() || null,
    };
    salvar.disabled = true;
    try {
      let pedido;
      if (idEdicao) {
        await api.patch(`/pedidos/${idEdicao}`, corpo);
        pedido = await api.put(`/pedidos/${idEdicao}/itens`, { itens });
        aviso("Alterações salvas.");
      } else {
        pedido = await api.post("/pedidos", { ...corpo, itens }, { cabecalhos: { "Idempotency-Key": chaveIdempotencia } });
        aviso(`Pedido ${pedido.numero} criado.`);
        if (confirmarDepois) {
          try {
            await api.post(`/pedidos/${pedido.id}/confirmar`);
            aviso("Pedido confirmado e estoque reservado.");
          } catch (erro) {
            avisarErro(erro);
          }
        }
      }
      ctx.navegar(`pedidos/${pedido.id}`);
    } catch (erro) {
      mostrarErros(erros, erro, form);
      window.scrollTo({ top: 0 });
    } finally {
      salvar.disabled = false;
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    enviar(false);
  });
  salvarConfirmar?.addEventListener("click", () => enviar(true));

  anexarFormulario();
  function anexarFormulario() {
    form.append(
      erros,
      h(
        "div",
        { class: "colunas" },
        h(
          "div",
          { class: "pilha" },
          bloco("Cliente e entrega", h("div", { class: "grade-form" }, h("label", { class: "campo largo" }, h("span", { text: "Cliente" }), caixaCliente, clienteEscolhido), campo("Depósito de saída", deposito, { dica: "A reserva é feita neste depósito." }), campo("Frete (R$)", frete))),
          bloco("Itens", h("div", { class: "pilha" }, h("label", { class: "campo" }, h("span", { text: "Adicionar produto" }), caixaProduto), h("div", { class: "mudo" }, `Seu limite de desconto por item é ${limiteDesconto}%.`), listaItens)),
        ),
        h("div", { class: "pilha" }, bloco("Resumo", resumo), bloco("Observações", campo("Visível para a equipe", observacoes))),
      ),
    );
  }
  desenharItens();

  alvo.append(
    cabecalhoPagina(idEdicao ? `Editar ${existente.numero}` : "Novo pedido", "Os preços vêm do cadastro do produto.", [salvarConfirmar, salvar].filter(Boolean), {
      href: idEdicao ? `#/pedidos/${idEdicao}` : "#/pedidos",
      texto: idEdicao ? existente.numero : "Pedidos",
    }),
    form,
  );
}
