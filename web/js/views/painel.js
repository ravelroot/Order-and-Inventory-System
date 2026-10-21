import { api } from "../api.js";
import { bloco, cabecalhoPagina, fmt, graficoBarras, h, link, listaBarras, selo, STATUS_PEDIDO, tabela } from "../ui.js";

const ETAPAS = [
  ["RASCUNHO", "Ainda sem reserva"],
  ["CONFIRMADO", "Estoque reservado"],
  ["SEPARADO", "Pronto para faturar"],
  ["FATURADO", "Aguardando envio"],
  ["ENVIADO", "Em trânsito"],
  ["ENTREGUE", "Concluídos"],
];

function esteira(d) {
  const etapas = ETAPAS.map(([status, dica]) =>
    h(
      "a",
      { class: `etapa st-${status}`, href: `#/pedidos?status=${status}` },
      h("span", { class: "etapa-quantidade", text: fmt.numero(d.pedidos_por_status[status] || 0) }),
      h("span", { class: "etapa-nome", text: STATUS_PEDIDO[status] }),
      h("span", { class: "etapa-dica", text: dica }),
    ),
  );
  const abertos = ["RASCUNHO", "CONFIRMADO", "SEPARADO"].reduce((s, k) => s + (d.pedidos_por_status[k] || 0), 0);
  return h(
    "section",
    { class: "bloco esteira", "aria-label": "Pedidos por etapa" },
    h("div", { class: "esteira-trilho" }, etapas),
    h(
      "div",
      { class: "esteira-rodape" },
      h("span", { text: `${fmt.numero(abertos)} pedido(s) ainda não faturado(s)` }),
      h("a", { href: "#/pedidos?status=CANCELADO", text: `${fmt.numero(d.pedidos_por_status.CANCELADO || 0)} cancelado(s)` }),
    ),
  );
}

function indicadores(d) {
  const variacao = d.variacao_percentual;
  const textoVariacao =
    variacao === null ? "Sem base no mês anterior" : `${variacao >= 0 ? "+" : ""}${fmt.percentual(variacao)} sobre o mesmo período do mês passado`;
  return h(
    "section",
    { class: "indicadores", "aria-label": "Indicadores do mês" },
    h(
      "div",
      { class: "indicador" },
      h("span", { text: "Faturado no mês" }),
      h("strong", { text: fmt.moeda(d.receita_mes) }),
      h("small", { class: variacao === null ? "" : variacao >= 0 ? "positivo" : "negativo", text: textoVariacao }),
    ),
    h(
      "div",
      { class: "indicador" },
      h("span", { text: "Ticket médio" }),
      h("strong", { text: fmt.moeda(d.ticket_medio_mes) }),
      h("small", { text: `${fmt.numero(d.pedidos_faturados_mes)} pedido(s) faturado(s)` }),
    ),
    h(
      "div",
      { class: "indicador" },
      h("span", { text: "Estoque a preço de custo" }),
      h("strong", { text: fmt.moeda(d.valor_estoque) }),
      h("small", { text: `${fmt.numero(d.unidades_em_estoque)} unidades nos depósitos` }),
    ),
    h(
      "div",
      { class: "indicador" },
      h("span", { text: "Abaixo do mínimo" }),
      h("strong", { class: d.produtos_abaixo_minimo ? "negativo" : "", text: `${fmt.numero(d.produtos_abaixo_minimo)} produto(s)` }),
      h("a", { href: "#/relatorios?aba=giro", text: d.produtos_em_ruptura ? `${d.produtos_em_ruptura} sem saldo; ver reposição` : "Ver sugestão de reposição" }),
    ),
  );
}

export async function render(alvo, ctx) {
  const d = await api.get("/relatorios/dashboard");
  const total30 = d.vendas_30_dias.reduce((s, v) => s + v.receita, 0);
  const acoes = ctx.pode("gerente", "vendedor") ? [link("Novo pedido", "#/pedidos/novo")] : [];
  alvo.append(
    cabecalhoPagina("Painel", `Situação em ${fmt.data(d.referencia)}`, acoes),
    h(
      "div",
      { class: "pilha" },
      esteira(d),
      indicadores(d),
      h(
        "div",
        { class: "colunas" },
        bloco(
          "Faturamento dos últimos 30 dias",
          graficoBarras(d.vendas_30_dias, { valor: (v) => v.receita, rotulo: (v) => v.rotulo }),
          { descricao: `${fmt.moeda(total30)} no período. A barra cinza é hoje, ainda em andamento.` },
        ),
        bloco(
          "Mais vendidos em 30 dias",
          d.top_produtos.length
            ? listaBarras(d.top_produtos, {
                rotulo: (p) => p.rotulo,
                valor: (p) => p.receita,
                detalhe: (p) => `${fmt.numero(p.quantidade)} un., margem ${fmt.percentual(p.margem_percentual)}`,
              })
            : h("p", { class: "mudo", text: "Nenhuma venda faturada no período." }),
        ),
      ),
      bloco(
        "Últimos pedidos",
        tabela({
          colunas: [
            { titulo: "Pedido", valor: (p) => h("a", { href: `#/pedidos/${p.id}`, class: "codigo", text: p.numero }) },
            { titulo: "Cliente", valor: (p) => p.cliente, classe: "principal" },
            { titulo: "Status", valor: (p) => selo(p.status) },
            { titulo: "Criado em", valor: (p) => fmt.dataHora(p.criado_em) },
            { titulo: "Total", valor: (p) => fmt.moeda(p.total), classe: "num" },
          ],
          linhas: d.ultimos_pedidos,
          aoClicar: (p) => ctx.navegar(`pedidos/${p.id}`),
          vazio: "Nenhum pedido ainda.",
        }),
        { acoes: [link("Ver todos", "#/pedidos", "botao secundario pequeno")], semCorpo: true },
      ),
    ),
  );
}
