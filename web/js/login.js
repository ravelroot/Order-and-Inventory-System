const form = document.getElementById("form-login");
const erro = document.getElementById("erro");
const entrar = document.getElementById("entrar");
const senha = document.getElementById("senha");
const mostrar = document.getElementById("mostrar");
const status = document.getElementById("status-servidor");
const parametros = new URLSearchParams(window.location.search);

function destino() {
  const voltar = parametros.get("voltar") || "";
  return /^#\/[\w/?=&.-]*$/.test(voltar) ? `/${voltar}` : "/#/painel";
}

function mostrarErro(texto) {
  erro.textContent = texto;
  erro.hidden = !texto;
}

let contagem;
function bloquear(segundos) {
  clearInterval(contagem);
  entrar.disabled = true;
  let restante = segundos;
  const atualizar = () => {
    mostrarErro(`Muitas tentativas seguidas. Tente de novo em ${restante} s.`);
    if (restante-- <= 0) {
      clearInterval(contagem);
      contagem = null;
      entrar.disabled = false;
      mostrarErro("");
    }
  };
  atualizar();
  contagem = setInterval(atualizar, 1000);
}

mostrar.addEventListener("click", () => {
  const visivel = senha.type === "text";
  senha.type = visivel ? "password" : "text";
  mostrar.setAttribute("aria-pressed", String(!visivel));
  mostrar.setAttribute("aria-label", visivel ? "Mostrar senha" : "Esconder senha");
});

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const usuario = form.usuario.value.trim();
  if (!usuario || !senha.value) {
    mostrarErro("Informe usuário e senha.");
    return;
  }
  entrar.disabled = true;
  entrar.textContent = "Entrando…";
  try {
    const resposta = await fetch("/api/v1/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ usuario, senha: senha.value }),
    });
    const dados = await resposta.json().catch(() => ({}));
    if (resposta.ok) {
      senha.value = "";
      window.location.replace(destino());
      return;
    }
    if (resposta.status === 429) {
      bloquear(Number(resposta.headers.get("Retry-After")) || 60);
      return;
    }
    mostrarErro(dados?.erro?.mensagem || "Não foi possível entrar.");
    senha.select();
  } catch {
    mostrarErro("Sem conexão com o servidor.");
  } finally {
    entrar.textContent = "Entrar";
    if (!contagem) entrar.disabled = false;
  }
});

if (parametros.get("motivo") === "expirou") mostrarErro("Sua sessão expirou. Entre novamente.");

fetch("/api/saude", { headers: { Accept: "application/json" } })
  .then((r) => (r.ok ? r.json() : Promise.reject()))
  .then((dados) => {
    status.textContent = `Servidor disponível, versão ${dados.versao}`;
  })
  .catch(() => {
    status.textContent = "Servidor indisponível no momento.";
  });

document.getElementById("usuario").focus();
