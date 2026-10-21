import { api } from "../api.js";
import {
  abrirGaveta,
  aviso,
  avisarErro,
  botao,
  cabecalhoPagina,
  campo,
  digitos,
  entrada,
  fmt,
  h,
  lerFormulario,
  limpar,
  mascaraCnpj,
  mostrarErros,
  paginacao,
  selecao,
  tabela,
} from "../ui.js";

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");

function abrirFormulario(fornecedor, aoSalvar) {
  const erros = h("div", { class: "erro-form", hidden: true });
  const cnpj = entrada({ name: "cnpj", value: fornecedor?.cnpj_formatado || "", inputmode: "numeric", required: true });
  cnpj.addEventListener("input", () => {
    cnpj.value = mascaraCnpj(cnpj.value);
  });
  const form = h(
    "form",
    { class: "grade-form", id: "form-fornecedor", novalidate: true },
    h("div", { class: "largo" }, erros),
    campo("Razão social", entrada({ name: "razao_social", value: fornecedor?.razao_social || "", required: true }), { largo: true }),
    campo("Nome fantasia", entrada({ name: "nome_fantasia", value: fornecedor?.nome_fantasia || "" })),
    campo("CNPJ", cnpj),
    campo("E-mail", entrada({ type: "email", name: "email", value: fornecedor?.email || "" })),
    campo("Telefone", entrada({ name: "telefone", value: fornecedor?.telefone || "" })),
    campo("Cidade", entrada({ name: "cidade", value: fornecedor?.cidade || "" })),
    campo("UF", selecao([["", "—"], ...UFS], { name: "uf", value: fornecedor?.uf || "" })),
    campo("Prazo de entrega (dias)", entrada({ type: "number", name: "prazo_entrega_dias", min: 0, value: fornecedor?.prazo_entrega_dias ?? 7 }), {
      dica: "Usado na sugestão de reposição.",
    }),
    h("label", { class: "marcador largo" }, h("input", { type: "checkbox", name: "ativo", checked: fornecedor ? fornecedor.ativo : true }), "Fornecedor ativo"),
  );
  const salvar = h("button", { class: "botao", type: "submit", text: fornecedor ? "Salvar fornecedor" : "Cadastrar fornecedor" });
  salvar.setAttribute("form", form.id);
  const modal = abrirGaveta({ titulo: fornecedor ? "Editar fornecedor" : "Novo fornecedor", conteudo: form, rodape: [salvar] });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const dados = lerFormulario(form);
    dados.cnpj = digitos(dados.cnpj);
    salvar.disabled = true;
    try {
      if (fornecedor) await api.put(`/fornecedores/${fornecedor.id}`, dados);
      else await api.post("/fornecedores", dados);
      modal.fechar();
      aviso(fornecedor ? "Fornecedor salvo." : "Fornecedor cadastrado.");
      aoSalvar();
    } catch (erro) {
      mostrarErros(erros, erro, form);
    } finally {
      salvar.disabled = false;
    }
  });
}

export async function lista(alvo, ctx) {
  const filtros = { q: "", pagina: 1 };
  const resultado = h("div");
  async function carregar() {
    try {
      const pagina = await api.get("/fornecedores", { ...filtros, por_pagina: 25 });
      limpar(
        resultado,
        tabela({
          colunas: [
            { titulo: "Fornecedor", valor: (f) => h("span", {}, f.nome_fantasia || f.razao_social, h("span", { class: "secundaria", text: f.razao_social })), classe: "principal" },
            { titulo: "CNPJ", valor: (f) => h("span", { class: "codigo", text: f.cnpj_formatado }) },
            { titulo: "Cidade", valor: (f) => (f.cidade ? `${f.cidade}/${f.uf}` : "—") },
            { titulo: "Prazo", valor: (f) => `${fmt.numero(f.prazo_entrega_dias)} dias`, classe: "num" },
            { titulo: "", valor: (f) => (f.ativo ? null : h("span", { class: "selo", text: "Inativo" })) },
          ],
          linhas: pagina.itens,
          aoClicar: ctx.gestao() ? (f) => abrirFormulario(f, carregar) : null,
          vazio: "Nenhum fornecedor encontrado.",
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
  const busca = entrada({ type: "search", placeholder: "Nome ou CNPJ" });
  let espera;
  busca.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      filtros.q = busca.value.trim();
      filtros.pagina = 1;
      carregar();
    }, 300);
  });
  alvo.append(
    cabecalhoPagina("Fornecedores", "Empresas fictícias usadas nos pedidos de compra.", ctx.gestao() ? [botao("Novo fornecedor", () => abrirFormulario(null, carregar), { iconeNome: "mais" })] : []),
    h("div", { class: "filtros" }, h("label", { class: "campo busca" }, h("span", { text: "Buscar" }), busca)),
    h("section", { class: "bloco" }, resultado),
  );
  await carregar();
}
