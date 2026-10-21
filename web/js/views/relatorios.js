import { api } from "../api.js";
import { avisarErro, baixarArquivo, botao, cabecalhoPagina, campo, entrada, fmt, graficoBarras, h, limpar, listaBarras, selecao, tabela } from "../ui.js";

const AGRUPAMENTOS = [
  ["dia", "Por dia"],
  ["semana", "Por semana"],
  ["mes", "Por mês"],
  ["categoria", "Por categoria"],
  ["produto", "Por produto"],
  ["vendedor", "Por vendedor"],
  ["cliente", "Por cliente"],
  ["uf", "Por estado (UF)"],
];

const SITUACOES = {
  ruptura: ["Sem saldo", "alerta"],
  critico: ["Acaba antes da reposição", "aviso"],
  ok: ["Saudável", "ok"],
  excesso: ["Excesso (mais de 180 dias)", ""],
  parado: ["Parado no período", ""],
  sem_movimento: ["Sem estoque e sem venda", ""],
};

function hojeLocal(deslocamentoDias = 0) {
  const d = new Date(Date.now() + deslocamentoDias * 86400000);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(d);
}

function rotuloColuna(agrupar) {
  const texto = AGRUPAMENTOS.find(([k]) => k === agrupar)[1].replace("Por ", "");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function vendas(area) {
  const filtros = { inicio: hojeLocal(-89), fim: hojeLocal(), agrupar: "semana" };
  const resultado = h("div", { class: "pilha" });
  const inicio = entrada({ type: "date", value: filtros.inicio });
  const fim = entrada({ type: "date", value: filtros.fim });
  const agrupar = selecao(AGRUPAMENTOS, { value: filtros.agrupar });

  async function carregar() {
    try {
      const d = await api.get("/relatorios/vendas", filtros);
      const temporal = ["dia", "semana", "mes"].includes(d.agrupar);
      const t = d.totais;
      limpar(
        resultado,
        h(
          "section",
          { class: "indicadores" },
          h("div", { class: "indicador" }, h("span", { text: "Receita de produtos" }), h("strong", { text: fmt.moeda(t.receita) })),
          h("div", { class: "indicador" }, h("span", { text: "Margem bruta" }), h("strong", { text: fmt.moeda(t.margem) }), h("small", { text: `${fmt.percentual(t.margem_percentual)} da receita` })),
          h("div", { class: "indicador" }, h("span", { text: "Pedidos faturados" }), h("strong", { text: fmt.numero(t.pedidos) })),
          h("div", { class: "indicador" }, h("span", { text: "Ticket médio" }), h("strong", { text: fmt.moeda(t.ticket_medio) })),
        ),
        h(
          "section",
          { class: "bloco" },
          h("div", { class: "bloco-corpo" }, temporal ? graficoBarras(d.linhas, { valor: (l) => l.receita, rotulo: (l) => l.rotulo }) : listaBarras(d.linhas.slice(0, 10), { rotulo: (l) => l.rotulo, valor: (l) => l.receita, detalhe: (l) => `margem ${fmt.percentual(l.margem_percentual)}` })),
          tabela({
            colunas: [
              { titulo: rotuloColuna(d.agrupar), valor: (l) => l.rotulo, classe: "principal" },
              { titulo: "Pedidos", valor: (l) => fmt.numero(l.pedidos), classe: "num" },
              { titulo: "Unidades", valor: (l) => fmt.numero(l.quantidade), classe: "num" },
              { titulo: "Receita", valor: (l) => fmt.moeda(l.receita), classe: "num" },
              { titulo: "Custo", valor: (l) => fmt.moeda(l.custo), classe: "num" },
              { titulo: "Margem", valor: (l) => fmt.percentual(l.margem_percentual), classe: "num" },
            ],
            linhas: temporal ? [...d.linhas].reverse() : d.linhas,
            vazio: "Nenhuma venda faturada no período.",
          }),
        ),
      );
    } catch (erro) {
      avisarErro(erro);
    }
  }
  for (const [el, chave] of [[inicio, "inicio"], [fim, "fim"], [agrupar, "agrupar"]]) {
    el.addEventListener("change", () => {
      filtros[chave] = el.value;
      carregar();
    });
  }
  limpar(
    area,
    h(
      "div",
      { class: "filtros" },
      campo("De", inicio),
      campo("Até", fim),
      campo("Agrupar", agrupar),
      botao("Baixar CSV", () => baixarArquivo(api.urlExportacao("/relatorios/vendas", { ...filtros, formato: "csv" })), { classe: "secundario", iconeNome: "baixar" }),
    ),
    resultado,
  );
  return carregar();
}

function curvaAbc(area) {
  const filtros = { inicio: hojeLocal(-89), fim: hojeLocal() };
  const resultado = h("section", { class: "bloco" });
  const inicio = entrada({ type: "date", value: filtros.inicio });
  const fim = entrada({ type: "date", value: filtros.fim });
  async function carregar() {
    try {
      const d = await api.get("/relatorios/curva-abc", filtros);
      const resumo = (classe, texto) =>
        h("div", {}, h("strong", { text: `${fmt.numero(d.resumo[classe].produtos)} produto(s)` }), h("span", { text: `Classe ${classe}: ${texto}, ${fmt.moeda(d.resumo[classe].receita)}` }));
      limpar(
        resultado,
        h("div", { class: "resumo-abc" }, resumo("A", "80% da receita"), resumo("B", "15% seguintes"), resumo("C", "5% finais")),
        tabela({
          colunas: [
            { titulo: "Classe", valor: (i) => h("span", { class: `selo ${i.classe === "A" ? "ok" : i.classe === "B" ? "aviso" : ""}`, text: i.classe }) },
            { titulo: "Produto", valor: (i) => h("a", { href: `#/produtos/${i.produto_id}` }, i.produto, h("span", { class: "secundaria codigo", text: i.sku })) },
            { titulo: "Unidades", valor: (i) => fmt.numero(i.quantidade), classe: "num" },
            { titulo: "Receita", valor: (i) => fmt.moeda(i.receita), classe: "num" },
            { titulo: "Participação", valor: (i) => fmt.percentual(i.participacao, 2), classe: "num" },
            { titulo: "Acumulado", valor: (i) => fmt.percentual(i.acumulado, 1), classe: "num" },
          ],
          linhas: d.itens,
          vazio: "Nenhuma venda faturada no período.",
        }),
      );
    } catch (erro) {
      avisarErro(erro);
    }
  }
  for (const [el, chave] of [[inicio, "inicio"], [fim, "fim"]]) {
    el.addEventListener("change", () => {
      filtros[chave] = el.value;
      carregar();
    });
  }
  limpar(
    area,
    h(
      "div",
      { class: "filtros" },
      campo("De", inicio),
      campo("Até", fim),
      botao("Baixar CSV", () => baixarArquivo(api.urlExportacao("/relatorios/curva-abc", { ...filtros, formato: "csv" })), { classe: "secundario", iconeNome: "baixar" }),
    ),
    resultado,
  );
  return carregar();
}

function giro(area) {
  const filtros = { dias: 90, situacao: "" };
  const resultado = h("section", { class: "bloco" });
  const fichas = h("div", { class: "fichas" });
  const dias = selecao([[30, "30 dias"], [60, "60 dias"], [90, "90 dias"], [180, "180 dias"]], { value: 90 });
  let dados;

  function desenhar() {
    const itens = filtros.situacao ? dados.itens.filter((i) => i.situacao === filtros.situacao) : dados.itens;
    limpar(
      fichas,
      [["", "Todos", dados.itens.length], ...Object.entries(SITUACOES).map(([k, [rotulo]]) => [k, rotulo, dados.resumo[k] || 0])]
        .filter(([k, , n]) => !k || n)
        .map(([k, rotulo, n]) =>
          h("button", {
            class: "ficha",
            type: "button",
            "aria-pressed": String(filtros.situacao === k),
            onclick: () => {
              filtros.situacao = k;
              desenhar();
            },
          }, rotulo, h("b", { text: ` ${n}` })),
        ),
    );
    limpar(
      resultado,
      tabela({
        colunas: [
          { titulo: "Situação", valor: (i) => h("span", { class: `selo ${SITUACOES[i.situacao][1]}`, text: SITUACOES[i.situacao][0] }) },
          { titulo: "Produto", valor: (i) => h("a", { href: `#/produtos/${i.produto_id}` }, i.produto, h("span", { class: "secundaria codigo", text: i.sku })) },
          { titulo: "Disponível", valor: (i) => fmt.numero(i.disponivel), classe: "num" },
          { titulo: "Mínimo", valor: (i) => fmt.numero(i.estoque_minimo), classe: "num" },
          { titulo: `Vendido (${dados.dias} d)`, valor: (i) => fmt.numero(i.vendido_periodo), classe: "num" },
          { titulo: "Por dia", valor: (i) => i.demanda_diaria.toLocaleString("pt-BR"), classe: "num" },
          { titulo: "Cobertura", valor: (i) => (i.cobertura_dias === null ? "—" : `${fmt.numero(Math.round(i.cobertura_dias))} d`), classe: "num" },
          { titulo: "Prazo fornec.", valor: (i) => `${i.prazo_fornecedor_dias} d`, classe: "num" },
          { titulo: "Comprar", valor: (i) => (i.sugestao_compra ? h("strong", { text: fmt.numero(i.sugestao_compra) }) : "—"), classe: "num" },
        ],
        linhas: itens,
        vazio: "Nenhum produto nessa situação.",
      }),
    );
  }

  async function carregar() {
    try {
      dados = await api.get("/relatorios/giro-estoque", { dias: filtros.dias });
      desenhar();
    } catch (erro) {
      avisarErro(erro);
    }
  }
  dias.addEventListener("change", () => {
    filtros.dias = Number(dias.value);
    carregar();
  });
  limpar(
    area,
    h("p", { class: "mudo", style: { marginBottom: "14px", maxWidth: "72ch" } }, "Cobertura = quantos dias o saldo disponível dura no ritmo de vendas do período. A sugestão de compra cobre o prazo do fornecedor mais 15 dias, acima do estoque mínimo."),
    h(
      "div",
      { class: "filtros" },
      campo("Período de vendas", dias),
      botao("Baixar CSV", () => baixarArquivo(api.urlExportacao("/relatorios/giro-estoque", { dias: filtros.dias, formato: "csv" })), { classe: "secundario", iconeNome: "baixar" }),
    ),
    fichas,
    resultado,
  );
  return carregar();
}

export async function render(alvo, ctx) {
  const abas = ctx.gestao()
    ? [["vendas", "Vendas", vendas], ["abc", "Curva ABC", curvaAbc], ["giro", "Reposição e giro", giro]]
    : [["giro", "Reposição e giro", giro]];
  const inicial = abas.find(([k]) => k === ctx.query.aba)?.[0] || abas[0][0];
  const area = h("div");
  const barra = h("div", { class: "abas", role: "tablist" });
  const botoes = abas.map(([chave, rotulo, desenhar]) => {
    const b = h("button", { type: "button", role: "tab", text: rotulo });
    b.addEventListener("click", () => {
      botoes.forEach((x) => x.setAttribute("aria-selected", String(x === b)));
      limpar(area, h("div", { class: "carregando", text: "Carregando…" }));
      desenhar(area);
    });
    b.dataset.chave = chave;
    return b;
  });
  barra.append(...botoes);
  alvo.append(cabecalhoPagina("Relatórios", "Valores de vendas consideram pedidos faturados, enviados ou entregues, sem frete.", []), barra, area);
  const ativo = botoes.find((b) => b.dataset.chave === inicial);
  ativo.setAttribute("aria-selected", "true");
  botoes.filter((b) => b !== ativo).forEach((b) => b.setAttribute("aria-selected", "false"));
  await abas.find(([k]) => k === inicial)[2](area);
}
