import { api } from "../api.js";
import {
  abrirGaveta,
  aviso,
  avisarErro,
  bloco,
  botao,
  cabecalhoPagina,
  campo,
  dinheiroParaApi,
  digitos,
  entrada,
  fmt,
  h,
  icone,
  lerFormulario,
  limpar,
  mascaraDocumento,
  mostrarErros,
  paginacao,
  selecao,
  selo,
  tabela,
} from "../ui.js";

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

async function abrirFormulario(cliente, ctx, aoSalvar) {
  let documento = cliente?.documento || "";
  if (cliente && documento.includes("*")) {
    documento = (await api.get(`/clientes/${cliente.id}/documento`)).documento;
  }
  const erros = h("div", { class: "erro-form", hidden: true });
  const tipo = selecao([["F", "Pessoa física"], ["J", "Pessoa jurídica"]], { name: "tipo_pessoa", value: cliente?.tipo_pessoa || "F" });
  const doc = entrada({ name: "documento", value: mascaraDocumento(documento, cliente?.tipo_pessoa), inputmode: "numeric", required: true });
  doc.addEventListener("input", () => {
    doc.value = mascaraDocumento(doc.value, tipo.value);
  });
  tipo.addEventListener("change", () => {
    doc.value = mascaraDocumento(doc.value, tipo.value);
  });
  const form = h(
    "form",
    { class: "grade-form", id: "form-cliente", novalidate: true },
    h("div", { class: "largo" }, erros),
    campo("Tipo", tipo),
    campo("CPF ou CNPJ", doc),
    campo("Nome ou razão social", entrada({ name: "nome", value: cliente?.nome || "", required: true }), { largo: true }),
    campo("E-mail", entrada({ type: "email", name: "email", value: cliente?.email || "" })),
    campo("Telefone com DDD", entrada({ name: "telefone", inputmode: "tel", value: cliente?.telefone || "" })),
    campo("CEP", entrada({ name: "cep", inputmode: "numeric", value: fmt.cep(cliente?.cep) === "—" ? "" : fmt.cep(cliente?.cep) })),
    campo("Logradouro", entrada({ name: "logradouro", value: cliente?.logradouro || "" }), { largo: true }),
    campo("Número", entrada({ name: "numero", value: cliente?.numero || "" })),
    campo("Complemento", entrada({ name: "complemento", value: cliente?.complemento || "" })),
    campo("Bairro", entrada({ name: "bairro", value: cliente?.bairro || "" })),
    campo("Cidade", entrada({ name: "cidade", value: cliente?.cidade || "" })),
    campo("UF", selecao([["", "—"], ...UFS], { name: "uf", value: cliente?.uf || "" })),
    campo("Limite de crédito (R$)", entrada({ name: "limite_credito", inputmode: "decimal", value: cliente ? String(cliente.limite_credito).replace(".", ",") : "0" }), {
      dica: "0 = sem limite. Pedidos acima do limite precisam da gerência.",
    }),
    h("label", { class: "marcador largo" }, h("input", { type: "checkbox", name: "ativo", checked: cliente ? cliente.ativo : true }), "Cliente ativo"),
  );
  const salvar = h("button", { class: "botao", type: "submit", text: cliente ? "Salvar cliente" : "Cadastrar cliente" });
  salvar.setAttribute("form", form.id);
  const modal = abrirGaveta({ titulo: cliente ? "Editar cliente" : "Novo cliente", conteudo: form, rodape: [salvar] });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const dados = lerFormulario(form);
    dados.documento = digitos(dados.documento);
    dados.limite_credito = dinheiroParaApi(dados.limite_credito) || "0";
    salvar.disabled = true;
    try {
      const salvo = cliente ? await api.put(`/clientes/${cliente.id}`, dados) : await api.post("/clientes", dados);
      modal.fechar();
      aviso(cliente ? "Cliente salvo." : "Cliente cadastrado.");
      aoSalvar?.(salvo);
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      salvar.disabled = false;
    }
  });
}

export async function lista(alvo, ctx) {
  const filtros = { q: "", tipo_pessoa: "", uf: "", pagina: 1 };
  const resultado = h("div");
  async function carregar() {
    try {
      const pagina = await api.get("/clientes", { ...filtros, por_pagina: 25 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Cliente", valor: (c) => h("span", {}, c.nome, h("span", { class: "secundaria", text: c.email || "" })), classe: "principal" },
            { titulo: "Documento", valor: (c) => h("span", { class: "codigo", text: c.documento }) },
            { titulo: "Cidade", valor: (c) => (c.cidade ? `${c.cidade}/${c.uf}` : "—") },
            { titulo: "Telefone", valor: (c) => fmt.telefone(c.telefone) },
            { titulo: "", valor: (c) => (c.ativo ? null : h("span", { class: "selo", text: "Inativo" })) },
          ],
          linhas: pagina.itens,
          aoClicar: (c) => ctx.navegar(`clientes/${c.id}`),
          vazio: "Nenhum cliente encontrado.",
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
  const busca = entrada({ type: "search", placeholder: "Nome, cidade ou parte do documento" });
  const tipo = selecao([["", "Todos"], ["F", "Pessoa física"], ["J", "Pessoa jurídica"]]);
  const uf = selecao([["", "Todas"], ...UFS]);
  let espera;
  busca.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      filtros.q = busca.value.trim();
      filtros.pagina = 1;
      carregar();
    }, 300);
  });
  for (const [el, chave] of [[tipo, "tipo_pessoa"], [uf, "uf"]]) {
    el.addEventListener("change", () => {
      filtros[chave] = el.value;
      filtros.pagina = 1;
      carregar();
    });
  }
  const descricao = ctx.gestao()
    ? "Clientes de demonstração com dados fictícios."
    : "Por proteção de dados, o CPF aparece mascarado. Abra o cliente para revelar quando precisar (fica registrado).";
  alvo.append(
    cabecalhoPagina("Clientes", descricao, ctx.pode("vendedor", "gerente") ? [botao("Novo cliente", () => abrirFormulario(null, ctx, (c) => ctx.navegar(`clientes/${c.id}`)), { iconeNome: "mais" })] : []),
    h("div", { class: "filtros" }, h("label", { class: "campo busca" }, h("span", { text: "Buscar" }), busca), campo("Tipo", tipo), campo("UF", uf)),
    h("section", { class: "bloco" }, resultado),
  );
  await carregar();
}

export async function detalhe(alvo, ctx) {
  const [id] = ctx.params;
  const [cliente, resumo, pedidos] = await Promise.all([
    api.get(`/clientes/${id}`),
    api.get(`/clientes/${id}/resumo`),
    api.get("/pedidos", { cliente_id: id, por_pagina: 10 }),
  ]);
  const documento = h("span", { class: "codigo", text: cliente.documento });
  const revelar = cliente.documento.includes("*") && ctx.pode("vendedor", "gerente")
    ? h(
        "button",
        {
          class: "botao texto pequeno",
          type: "button",
          onclick: async (e) => {
            try {
              documento.textContent = (await api.get(`/clientes/${id}/documento`)).documento;
              e.currentTarget.remove();
            } catch (erro) {
              avisarErro(erro);
            }
          },
        },
        icone("olho"),
        "Revelar",
      )
    : null;
  const endereco = [cliente.logradouro && `${cliente.logradouro}, ${cliente.numero || "s/n"}`, cliente.complemento, cliente.bairro, cliente.cidade && `${cliente.cidade}/${cliente.uf}`, cliente.cep && `CEP ${fmt.cep(cliente.cep)}`]
    .filter(Boolean)
    .join(", ");

  const acoes = ctx.pode("vendedor", "gerente")
    ? [
        botao("Editar", () => abrirFormulario(cliente, ctx, () => window.dispatchEvent(new HashChangeEvent("hashchange"))), { classe: "secundario" }),
        h("a", { class: "botao", href: "#/pedidos/novo", text: "Novo pedido" }),
      ]
    : [];

  alvo.append(
    cabecalhoPagina(cliente.nome, cliente.tipo_pessoa === "J" ? "Pessoa jurídica" : "Pessoa física", acoes, { href: "#/clientes", texto: "Clientes" }),
    h(
      "section",
      { class: "indicadores", style: { marginBottom: "20px" } },
      h("div", { class: "indicador" }, h("span", { text: "Total comprado" }), h("strong", { text: fmt.moeda(resumo.total_comprado) })),
      h("div", { class: "indicador" }, h("span", { text: "Pedidos faturados" }), h("strong", { text: fmt.numero(resumo.pedidos_faturados) })),
      h("div", { class: "indicador" }, h("span", { text: "Ticket médio" }), h("strong", { text: fmt.moeda(resumo.ticket_medio) })),
      h("div", { class: "indicador" }, h("span", { text: "Última compra" }), h("strong", { text: fmt.data(resumo.ultima_compra) })),
    ),
    h(
      "div",
      { class: "colunas" },
      bloco(
        "Pedidos recentes",
        tabela({
          colunas: [
            { titulo: "Pedido", valor: (p) => h("a", { href: `#/pedidos/${p.id}`, class: "codigo", text: p.numero }) },
            { titulo: "Status", valor: (p) => selo(p.status) },
            { titulo: "Criado em", valor: (p) => fmt.dataHora(p.criado_em) },
            { titulo: "Total", valor: (p) => fmt.moeda(p.total), classe: "num" },
          ],
          linhas: pedidos.itens,
          aoClicar: (p) => ctx.navegar(`pedidos/${p.id}`),
          vazio: "Este cliente ainda não fez pedidos.",
        }),
        { semCorpo: true, acoes: pedidos.total > 10 ? [h("a", { class: "botao secundario pequeno", href: `#/pedidos?q=${encodeURIComponent(cliente.nome)}`, text: `Ver os ${pedidos.total}` })] : null },
      ),
      bloco(
        "Cadastro",
        h(
          "dl",
          { class: "definicoes" },
          h("dt", { text: cliente.tipo_pessoa === "J" ? "CNPJ" : "CPF" }),
          h("dd", {}, documento, " ", revelar),
          h("dt", { text: "E-mail" }),
          h("dd", { text: cliente.email || "—" }),
          h("dt", { text: "Telefone" }),
          h("dd", { text: fmt.telefone(cliente.telefone) }),
          h("dt", { text: "Endereço" }),
          h("dd", { text: endereco || "—" }),
          h("dt", { text: "Limite de crédito" }),
          h("dd", { text: Number(cliente.limite_credito) ? fmt.moeda(cliente.limite_credito) : "Sem limite" }),
          h("dt", { text: "Cliente desde" }),
          h("dd", { text: fmt.data(cliente.criado_em) }),
        ),
      ),
    ),
  );
}
