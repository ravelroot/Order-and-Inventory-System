const SVG_NS = "http://www.w3.org/2000/svg";

export function h(tag, atributos = {}, ...filhos) {
  const el = document.createElement(tag);
  let valorInicial;
  for (const [chave, valor] of Object.entries(atributos || {})) {
    if (valor === undefined || valor === null || valor === false) continue;
    if (chave === "value") valorInicial = valor;
    else if (chave === "class") el.className = valor;
    else if (chave === "text") el.textContent = valor;
    else if (chave === "style") Object.assign(el.style, valor);
    else if (chave === "dataset") Object.assign(el.dataset, valor);
    else if (chave.startsWith("on") && typeof valor === "function") el.addEventListener(chave.slice(2), valor);
    else if (chave in el && typeof valor !== "string") el[chave] = valor;
    else el.setAttribute(chave, valor === true ? "" : valor);
  }
  anexar(el, filhos);
  if (valorInicial !== undefined) {
    el.value = valorInicial;
    if (tag === "input") el.defaultValue = valorInicial;
  }
  return el;
}

export function anexar(el, filhos) {
  for (const filho of filhos.flat(Infinity)) {
    if (filho === null || filho === undefined || filho === false) continue;
    el.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
  return el;
}

export function limpar(el, ...filhos) {
  el.replaceChildren();
  return anexar(el, filhos);
}

const ICONES = {
  painel: "M3 13h8V3H3zm10 8h8V11h-8zM3 21h8v-6H3zm10-18v6h8V3z",
  pedidos: "M6 2h9l5 5v15H6zM14 2v6h6M9 13h8M9 17h8M9 9h3",
  produtos: "M21 8l-9-5-9 5 9 5 9-5zM3 8v8l9 5 9-5V8M12 13v8",
  estoque: "M3 21V8l9-5 9 5v13M7 21v-8h10v8M7 17h10",
  compras: "M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm9 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  clientes: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm13 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  fornecedores: "M1 3h15v13H1zM16 8h4l3 3v5h-7M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zm13 0a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  relatorios: "M3 3v18h18M7 15l4-4 3 3 6-6",
  usuarios: "M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm-9 10a9 9 0 0 1 18 0",
  auditoria: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4",
  mais: "M12 5v14M5 12h14",
  fechar: "M18 6L6 18M6 6l12 12",
  lixeira: "M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6",
  baixar: "M12 3v12M7 10l5 5 5-5M5 21h14",
  menu: "M3 6h18M3 12h18M3 18h18",
  lua: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  sol: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  olho: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12zm11 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  sair: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9",
  chave: "M21 2l-2 2m-7.6 7.6a5.5 5.5 0 1 1-7.8 7.8 5.5 5.5 0 0 1 7.8-7.8zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4",
};

export function icone(nome) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const caminho = document.createElementNS(SVG_NS, "path");
  caminho.setAttribute("d", ICONES[nome] || "");
  svg.append(caminho);
  return svg;
}

export function svg(tag, atributos = {}, ...filhos) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (chave === "text") el.textContent = valor;
    else if (chave.startsWith("on") && typeof valor === "function") el.addEventListener(chave.slice(2), valor);
    else if (valor !== undefined && valor !== null) el.setAttribute(chave, valor);
  }
  filhos.flat().forEach((f) => f && el.append(f));
  return el;
}

const moedaFmt = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const moedaCurta = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", notation: "compact", maximumFractionDigits: 1 });
const numeroFmt = new Intl.NumberFormat("pt-BR");
const dataFmt = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric" });
const dataHoraFmt = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "2-digit",
  year: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

export const fmt = {
  moeda: (v) => (v === null || v === undefined ? "—" : moedaFmt.format(v)),
  moedaCurta: (v) => moedaCurta.format(v || 0),
  numero: (v) => (v === null || v === undefined ? "—" : numeroFmt.format(v)),
  percentual: (v, casas = 1) => (v === null || v === undefined ? "—" : `${Number(v).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`),
  data: (v) => (v ? dataFmt.format(new Date(v.length === 10 ? `${v}T12:00:00` : v)) : "—"),
  dataHora: (v) => (v ? dataHoraFmt.format(new Date(v)) : "—"),
  cep: (v) => (v && v.length === 8 ? `${v.slice(0, 5)}-${v.slice(5)}` : v || "—"),
  telefone: (v) => {
    if (!v) return "—";
    if (v.length === 11) return `(${v.slice(0, 2)}) ${v.slice(2, 7)}-${v.slice(7)}`;
    if (v.length === 10) return `(${v.slice(0, 2)}) ${v.slice(2, 6)}-${v.slice(6)}`;
    return v;
  },
};

export const STATUS_PEDIDO = {
  RASCUNHO: "Rascunho",
  CONFIRMADO: "Confirmado",
  SEPARADO: "Separado",
  FATURADO: "Faturado",
  ENVIADO: "Enviado",
  ENTREGUE: "Entregue",
  CANCELADO: "Cancelado",
};

export const STATUS_COMPRA = {
  RASCUNHO: "Rascunho",
  ENVIADO: "Enviado ao fornecedor",
  RECEBIDO_PARCIAL: "Recebido em parte",
  RECEBIDO: "Recebido",
  CANCELADO: "Cancelado",
};

export const PAPEIS = { admin: "Administração", gerente: "Gerência", vendedor: "Vendas", estoquista: "Estoque" };

export const TIPOS_MOV = {
  ENTRADA: "Entrada",
  SAIDA: "Saída (faturamento)",
  AJUSTE_POSITIVO: "Ajuste (+)",
  AJUSTE_NEGATIVO: "Ajuste (−)",
  TRANSFERENCIA_SAIDA: "Transferência (saída)",
  TRANSFERENCIA_ENTRADA: "Transferência (entrada)",
  RESERVA: "Reserva",
  LIBERACAO_RESERVA: "Reserva liberada",
  ESTORNO: "Estorno",
};

export function selo(status, rotulos = STATUS_PEDIDO) {
  return h("span", { class: `status st-${status}`, text: rotulos[status] || status });
}

export function aviso(mensagem, tipo = "ok") {
  let pilha = document.querySelector(".notificacoes");
  if (!pilha) {
    pilha = h("div", { class: "notificacoes", role: "status", "aria-live": "polite" });
    document.body.append(pilha);
  }
  const item = h("div", { class: `notificacao ${tipo === "erro" ? "erro" : ""}`, text: mensagem });
  pilha.append(item);
  setTimeout(() => item.remove(), tipo === "erro" ? 6000 : 3500);
}

export function avisarErro(erro) {
  aviso(erro?.message || "Algo deu errado.", "erro");
}

function montarModal(classe, { titulo, conteudo, rodape, aoFechar, centro }) {
  const anterior = document.activeElement;
  const corpo = h("div", { class: "modal-corpo" }, conteudo);
  const tituloId = `m-${Math.random().toString(36).slice(2, 8)}`;
  const botaoFechar = h("button", { class: "icone-botao", type: "button", "aria-label": "Fechar" }, icone("fechar"));
  const caixa = h(
    "div",
    { class: classe, role: "dialog", "aria-modal": "true", "aria-labelledby": tituloId },
    h("div", { class: "modal-cabecalho" }, h("h2", { id: tituloId, text: titulo }), botaoFechar),
    corpo,
    rodape ? h("div", { class: "modal-rodape" }, rodape) : null,
  );
  const fundo = h("div", { class: `fundo-modal ${centro ? "centro" : ""}` }, caixa);
  const fechar = () => {
    fundo.remove();
    document.removeEventListener("keydown", teclas);
    if (anterior instanceof HTMLElement) anterior.focus();
    aoFechar?.();
  };
  const teclas = (e) => {
    if (e.key === "Escape") fechar();
  };
  botaoFechar.addEventListener("click", fechar);
  fundo.addEventListener("mousedown", (e) => {
    if (e.target === fundo) fechar();
  });
  document.addEventListener("keydown", teclas);
  document.body.append(fundo);
  requestAnimationFrame(() => {
    const foco = caixa.querySelector("input:not([type=hidden]), select, textarea, .modal-rodape .botao");
    (foco || botaoFechar).focus();
  });
  return { fechar, corpo, caixa };
}

export const abrirGaveta = (opcoes) => montarModal("gaveta", opcoes);
export const abrirDialogo = (opcoes) => montarModal("dialogo", { ...opcoes, centro: true });

export function confirmar({ titulo, texto, acao = "Confirmar", perigo = false }) {
  return new Promise((resolver) => {
    let resposta = false;
    const sim = h("button", { class: `botao ${perigo ? "perigo" : ""}`, type: "button", text: acao });
    const nao = h("button", { class: "botao secundario", type: "button", text: "Voltar" });
    const modal = abrirDialogo({ titulo, conteudo: h("p", { text: texto }), rodape: [nao, sim], aoFechar: () => resolver(resposta) });
    sim.addEventListener("click", () => {
      resposta = true;
      modal.fechar();
    });
    nao.addEventListener("click", () => modal.fechar());
  });
}

export function campo(rotulo, controle, { dica, largo, nome } = {}) {
  if (nome && !controle.name) controle.name = nome;
  return h(
    "label",
    { class: `campo ${largo ? "largo" : ""}` },
    h("span", { text: rotulo }),
    controle,
    dica ? h("small", { text: dica }) : null,
  );
}

export function entrada(atributos = {}) {
  return h("input", { type: "text", autocomplete: "off", ...atributos });
}

export function selecao(opcoes, atributos = {}) {
  const el = h("select", atributos);
  for (const op of opcoes) {
    const [valor, rotulo] = Array.isArray(op) ? op : [op, op];
    el.append(h("option", { value: valor ?? "", text: rotulo }));
  }
  if (atributos.value !== undefined) el.value = atributos.value ?? "";
  return el;
}

export function lerFormulario(form) {
  const dados = {};
  for (const el of form.querySelectorAll("[name]")) {
    if (el.type === "checkbox") dados[el.name] = el.checked;
    else if (el.type === "number") dados[el.name] = el.value === "" ? null : Number(el.value);
    else dados[el.name] = el.value.trim() === "" ? null : el.value.trim();
  }
  return dados;
}

export function mostrarErros(area, erro, form) {
  form?.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
  form?.querySelectorAll(".erro-campo").forEach((el) => el.remove());
  if (!erro) {
    limpar(area);
    area.hidden = true;
    return;
  }
  const lista = [];
  if (Array.isArray(erro.detalhes)) {
    for (const d of erro.detalhes) {
      const nome = d.campo?.split(".")[0];
      const alvo = nome && form?.querySelector(`[name="${CSS.escape(nome)}"]`);
      if (alvo) {
        alvo.setAttribute("aria-invalid", "true");
        alvo.closest(".campo")?.append(h("span", { class: "erro-campo", text: d.mensagem }));
      } else {
        lista.push(d.campo ? `${d.campo}: ${d.mensagem || ""}` : d.mensagem || JSON.stringify(d));
      }
    }
  }
  limpar(area, h("strong", { text: erro.message }), lista.length ? h("ul", {}, lista.map((t) => h("li", { text: t }))) : null);
  area.hidden = false;
}

export function tabela({ colunas, linhas, aoClicar, vazio = "Nada encontrado.", rodape }) {
  if (!linhas.length) {
    return h("div", { class: "vazio" }, typeof vazio === "string" ? h("strong", { text: vazio }) : vazio);
  }
  const cabecalho = h("tr", {}, colunas.map((c) => h("th", { class: c.classe || "", scope: "col", text: c.titulo })));
  const corpo = linhas.map((linha) => {
    const tr = h(
      "tr",
      { class: aoClicar ? "clicavel" : "" },
      colunas.map((c) => {
        const valor = c.valor(linha);
        return h("td", { class: c.classe || "" }, valor);
      }),
    );
    if (aoClicar) {
      tr.tabIndex = 0;
      tr.addEventListener("click", (e) => {
        if (!e.target.closest("a, button")) aoClicar(linha);
      });
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter") aoClicar(linha);
      });
    }
    return tr;
  });
  return h(
    "div",
    { class: "tabela-rolagem" },
    h("table", {}, h("thead", {}, cabecalho), h("tbody", {}, corpo), rodape ? h("tfoot", {}, rodape) : null),
  );
}

export function paginacao(pagina, aoMudar) {
  if (!pagina || pagina.total === 0) return null;
  const inicio = (pagina.pagina - 1) * pagina.por_pagina + 1;
  const fim = Math.min(pagina.total, pagina.pagina * pagina.por_pagina);
  const anterior = h("button", { class: "botao secundario pequeno", type: "button", text: "Anterior", disabled: pagina.pagina <= 1 });
  const proxima = h("button", { class: "botao secundario pequeno", type: "button", text: "Próxima", disabled: pagina.pagina >= pagina.paginas });
  anterior.addEventListener("click", () => aoMudar(pagina.pagina - 1));
  proxima.addEventListener("click", () => aoMudar(pagina.pagina + 1));
  return h(
    "div",
    { class: "paginacao" },
    h("span", { text: `${fmt.numero(inicio)}–${fmt.numero(fim)} de ${fmt.numero(pagina.total)}` }),
    h("div", { class: "acoes" }, anterior, proxima),
  );
}

export function adiar(funcao, ms = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => funcao(...args), ms);
  };
}

export function autocompletar(input, buscar, aoEscolher) {
  const lista = h("ul", { class: "sugestoes", role: "listbox", hidden: true });
  const caixa = h("div", { class: "autocompletar" });
  input.replaceWith(caixa);
  caixa.append(input, lista);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-expanded", "false");
  input.setAttribute("aria-autocomplete", "list");
  let itens = [];
  let ativo = -1;

  const fechar = () => {
    lista.hidden = true;
    input.setAttribute("aria-expanded", "false");
    ativo = -1;
  };
  const marcar = () => [...lista.children].forEach((li, i) => li.setAttribute("aria-selected", String(i === ativo)));
  const escolher = (i) => {
    const item = itens[i];
    if (!item) return;
    fechar();
    aoEscolher(item);
  };
  const atualizar = adiar(async () => {
    const termo = input.value.trim();
    if (termo.length < 1) return fechar();
    try {
      itens = await buscar(termo);
    } catch {
      itens = [];
    }
    limpar(
      lista,
      itens.length
        ? itens.map((item, i) =>
            h(
              "li",
              { role: "option", onmousedown: (e) => (e.preventDefault(), escolher(i)) },
              h("strong", { text: item.rotulo }),
              h("span", { text: item.detalhe || "" }),
            ),
          )
        : h("li", { "aria-disabled": "true" }, h("span", { text: "Nenhum resultado" })),
    );
    ativo = itens.length ? 0 : -1;
    marcar();
    lista.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }, 220);

  input.addEventListener("input", atualizar);
  input.addEventListener("blur", () => setTimeout(fechar, 120));
  input.addEventListener("keydown", (e) => {
    if (lista.hidden) return;
    if (e.key === "ArrowDown") ativo = Math.min(itens.length - 1, ativo + 1);
    else if (e.key === "ArrowUp") ativo = Math.max(0, ativo - 1);
    else if (e.key === "Enter") {
      e.preventDefault();
      return escolher(ativo);
    } else if (e.key === "Escape") return fechar();
    else return;
    e.preventDefault();
    marcar();
  });
  return caixa;
}

export function graficoBarras(serie, { altura = 180, rotulo = (d) => d.rotulo, valor = (d) => d.valor, formatar = fmt.moeda } = {}) {
  const largura = 720;
  const margem = { topo: 10, direita: 6, base: 22, esquerda: 6 };
  const max = Math.max(1, ...serie.map(valor));
  const passo = (largura - margem.esquerda - margem.direita) / Math.max(serie.length, 1);
  const larguraBarra = Math.max(2, passo * 0.68);
  const util = altura - margem.topo - margem.base;
  const grafico = svg("svg", { class: "grafico", viewBox: `0 0 ${largura} ${altura}`, role: "img" });
  for (const fracao of [0.5, 1]) {
    const y = margem.topo + util * (1 - fracao);
    grafico.append(svg("line", { class: "grade", x1: 0, x2: largura, y1: y, y2: y }));
  }
  serie.forEach((d, i) => {
    const v = valor(d);
    const alturaBarra = Math.max(v > 0 ? 2 : 0, (v / max) * util);
    const x = margem.esquerda + i * passo + (passo - larguraBarra) / 2;
    const y = margem.topo + util - alturaBarra;
    const barra = svg("rect", { class: `barra ${i === serie.length - 1 ? "hoje" : ""}`, x, y, width: larguraBarra, height: alturaBarra, rx: 2 });
    barra.append(svg("title", { text: `${rotulo(d)}: ${formatar(v)}` }));
    grafico.append(barra);
    const passoRotulo = serie.length <= 10 ? 1 : Math.ceil(serie.length / 8);
    const ultimoRegular = Math.floor((serie.length - 1) / passoRotulo) * passoRotulo;
    const mostrarRotulo =
      i % passoRotulo === 0 || (i === serie.length - 1 && serie.length - 1 - ultimoRegular >= passoRotulo * 0.6);
    if (mostrarRotulo) {
      grafico.append(svg("text", { class: "eixo", x: x + larguraBarra / 2, y: altura - 6, "text-anchor": "middle", text: rotulo(d) }));
    }
  });
  const total = serie.reduce((s, d) => s + valor(d), 0);
  grafico.setAttribute("aria-label", `Gráfico de barras com ${serie.length} períodos, total ${formatar(total)}, máximo ${formatar(max)}`);
  return grafico;
}

export function listaBarras(itens, { rotulo, valor, formatar = fmt.moeda, detalhe }) {
  const max = Math.max(1, ...itens.map(valor));
  return h(
    "ul",
    { class: "lista-barras" },
    itens.map((item) =>
      h(
        "li",
        {},
        h("div", { class: "linha-topo" }, h("span", { text: rotulo(item), title: rotulo(item) }), h("strong", { text: formatar(valor(item)) })),
        h("div", { class: "trilho-barra" }, h("i", { style: { width: `${(valor(item) / max) * 100}%` } })),
        detalhe ? h("small", { class: "mudo", text: detalhe(item) }) : null,
      ),
    ),
  );
}

export function baixarArquivo(url) {
  const a = h("a", { href: url, download: "" });
  document.body.append(a);
  a.click();
  a.remove();
}

export function cabecalhoPagina(titulo, descricao, acoes = [], voltar = null) {
  return h(
    "header",
    { class: "cabecalho-pagina" },
    h(
      "div",
      {},
      voltar ? h("a", { class: "voltar", href: voltar.href, text: voltar.texto }) : null,
      h("h1", { text: titulo }),
      descricao ? h("p", { text: descricao }) : null,
    ),
    acoes.length ? h("div", { class: "acoes" }, acoes) : null,
  );
}

export function botao(texto, aoClicar, { classe = "", iconeNome, tipo = "button", ...resto } = {}) {
  return h("button", { class: `botao ${classe}`, type: tipo, onclick: aoClicar, ...resto }, iconeNome ? icone(iconeNome) : null, texto);
}

export function link(texto, href, classe = "botao") {
  return h("a", { class: classe, href, text: texto });
}

export function bloco(titulo, conteudo, { descricao, acoes, semCorpo } = {}) {
  return h(
    "section",
    { class: "bloco" },
    titulo || acoes
      ? h(
          "div",
          { class: "bloco-cabecalho" },
          h("div", {}, titulo ? h("h2", { text: titulo }) : null, descricao ? h("p", { text: descricao }) : null),
          acoes ? h("div", { class: "acoes" }, acoes) : null,
        )
      : null,
    semCorpo ? conteudo : h("div", { class: "bloco-corpo" }, conteudo),
  );
}

export function dinheiroParaApi(texto) {
  if (texto === null || texto === undefined || texto === "") return null;
  const limpo = String(texto).replace(/[^\d,.-]/g, "");
  return limpo.includes(",") ? limpo.replace(/\./g, "").replace(",", ".") : limpo;
}

export function digitos(texto) {
  return (texto || "").replace(/\D/g, "");
}

export function mascaraCpf(valor) {
  const d = digitos(valor).slice(0, 11);
  return d.replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

export function mascaraCnpj(valor) {
  const d = digitos(valor).slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

export function mascaraDocumento(valor, tipo) {
  if (tipo === "J") return mascaraCnpj(valor);
  if (tipo === "F") return mascaraCpf(valor);
  return digitos(valor).length > 11 ? mascaraCnpj(valor) : mascaraCpf(valor);
}
