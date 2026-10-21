const BASE = "/api/v1";

export class ErroApi extends Error {
  constructor(status, corpo) {
    const erro = corpo?.erro ?? {};
    super(erro.mensagem || `Erro ${status}`);
    this.status = status;
    this.codigo = erro.codigo || "erro";
    this.detalhes = erro.detalhes;
  }
}

function montarUrl(caminho, parametros) {
  const url = new URL(BASE + caminho, window.location.origin);
  for (const [chave, valor] of Object.entries(parametros || {})) {
    if (valor === undefined || valor === null || valor === "" || valor === false) continue;
    if (Array.isArray(valor)) valor.forEach((v) => url.searchParams.append(chave, v));
    else url.searchParams.set(chave, valor);
  }
  return url;
}

function irParaLogin(motivo) {
  const voltar = encodeURIComponent(window.location.hash || "#/painel");
  window.location.replace(`/login?voltar=${voltar}${motivo ? `&motivo=${motivo}` : ""}`);
}

export async function requisitar(metodo, caminho, { corpo, parametros, cabecalhos } = {}) {
  const opcoes = {
    method: metodo,
    credentials: "same-origin",
    headers: { Accept: "application/json", ...(cabecalhos || {}) },
  };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  let resposta;
  try {
    resposta = await fetch(montarUrl(caminho, parametros), opcoes);
  } catch {
    throw new ErroApi(0, { erro: { codigo: "rede", mensagem: "Sem conexão com o servidor." } });
  }
  const texto = await resposta.text();
  const dados = texto ? JSON.parse(texto) : null;
  if (resposta.status === 401 && !caminho.startsWith("/auth/login")) {
    irParaLogin(dados?.erro?.codigo === "sessao_expirada" ? "expirou" : "");
    throw new ErroApi(401, dados);
  }
  if (!resposta.ok) throw new ErroApi(resposta.status, dados);
  return dados;
}

export const api = {
  get: (caminho, parametros) => requisitar("GET", caminho, { parametros }),
  post: (caminho, corpo, opcoes = {}) => requisitar("POST", caminho, { corpo, ...opcoes }),
  put: (caminho, corpo) => requisitar("PUT", caminho, { corpo }),
  patch: (caminho, corpo) => requisitar("PATCH", caminho, { corpo }),
  urlExportacao: (caminho, parametros) => montarUrl(caminho, parametros).toString(),
  sair: async () => {
    try {
      await requisitar("POST", "/auth/logout");
    } finally {
      window.location.replace("/login");
    }
  },
};
