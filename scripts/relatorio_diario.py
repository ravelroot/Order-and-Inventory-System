import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
FUSO = ZoneInfo("America/Sao_Paulo")
ARQUIVO = RAIZ / "docs" / "relatorio-diario.md"
SAIDA_TESTES = RAIZ / "resultado-testes.txt"
LIMITE_HISTORICO = 30
STATUS = {
    "RASCUNHO": "Rascunho",
    "CONFIRMADO": "Confirmado",
    "SEPARADO": "Separado",
    "FATURADO": "Faturado",
    "ENVIADO": "Enviado",
    "ENTREGUE": "Entregue",
    "CANCELADO": "Cancelado",
}
SITUACAO = {"ruptura": "Sem saldo", "critico": "Acaba antes da reposição"}


def moeda(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def numero(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def decimal_br(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def cobertura(dias: float | None) -> str:
    return "—" if dias is None else f"{dias:.0f} dias"


def ler_testes() -> dict:
    resultado = {"passaram": 0, "falharam": 0, "ignorados": 0, "erros": 0, "duracao": None, "disponivel": False}
    if not SAIDA_TESTES.exists():
        return resultado
    texto = SAIDA_TESTES.read_text(encoding="utf-8", errors="replace")
    resumo = [linha for linha in texto.splitlines() if re.search(r"\d+ (passed|failed|error)", linha)]
    if not resumo:
        return resultado
    linha = resumo[-1]
    for chave, termo in (("passaram", "passed"), ("falharam", "failed"), ("ignorados", "skipped"), ("erros", "error")):
        achado = re.search(rf"(\d+) {termo}", linha)
        if achado:
            resultado[chave] = int(achado.group(1))
    duracao = re.search(r"in ([\d.]+)s", linha)
    if duracao:
        resultado["duracao"] = float(duracao.group(1))
    resultado["disponivel"] = True
    return resultado


def simular_operacao(agora: datetime) -> tuple[dict, dict]:
    os.environ["DATABASE_URL"] = "sqlite:///" + (RAIZ / "dados" / "relatorio_diario.db").as_posix()
    os.environ["AMBIENTE"] = "dev"

    from app.database import Base, SessaoLocal, engine
    from app.seguranca import gerar_senha_aleatoria
    from app.servicos import relatorios
    from scripts.popular_banco import Populador

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    semente = int(agora.strftime("%Y%m%d"))
    with SessaoLocal() as sessao:
        populador = Populador(sessao, semente, meses=3, total_pedidos=350, total_clientes=120, total_produtos=60)
        populador.u = populador.usuarios(gerar_senha_aleatoria())
        populador.estrutura()
        populador.carga_inicial()
        populador.pedidos()
        populador.inventario_final()
        painel = relatorios.dashboard(sessao)
        giro = relatorios.giro_estoque(sessao, 30)
    engine.dispose()
    return painel, giro


def ler_historico() -> list[str]:
    if not ARQUIVO.exists():
        return []
    texto = ARQUIVO.read_text(encoding="utf-8")
    if "## Histórico" not in texto:
        return []
    trecho = texto.split("## Histórico", 1)[1]
    return [linha for linha in trecho.splitlines() if re.match(r"\| \d{2}/\d{2}/\d{4} \|", linha)]


def montar(agora: datetime, testes: dict, painel: dict, giro: dict) -> str:
    data = agora.strftime("%d/%m/%Y")
    if not testes["disponivel"]:
        situacao_testes = "não executados"
    elif testes["falharam"] or testes["erros"]:
        situacao_testes = f"{testes['falharam'] + testes['erros']} com falha"
    else:
        situacao_testes = "todos passaram"

    linhas = [
        '<p align="center">',
        "  <picture>",
        '    <source media="(prefers-color-scheme: dark)" srcset="img/logo/logo-escuro.svg">',
        '    <img src="img/logo/logo-claro.svg" alt="Logo do Doca" width="72">',
        "  </picture>",
        "</p>",
        "",
        "# Relatório diário",
        "",
        f"Gerado automaticamente em {data} às {agora.strftime('%H:%M')} (horário de Brasília) pelo GitHub Actions.",
        "",
        "A operação abaixo é **simulada com dados fictícios**, gerados a cada dia com uma semente diferente,"
        " para mostrar o sistema funcionando de ponta a ponta.",
        "",
        "## Saúde do código",
        "",
        "| Indicador | Resultado |",
        "|---|---|",
        f"| Situação | {situacao_testes} |",
        f"| Testes que passaram | {testes['passaram']} |",
        f"| Testes com falha | {testes['falharam'] + testes['erros']} |",
        f"| Testes ignorados | {testes['ignorados']} |",
        f"| Duração | {decimal_br(testes['duracao'])} s |" if testes["duracao"] is not None else "| Duração | — |",
        "",
        "## Operação simulada do mês",
        "",
        "| Indicador | Valor |",
        "|---|---|",
        f"| Faturamento do mês | {moeda(painel['receita_mes'])} |",
        f"| Pedidos faturados | {numero(painel['pedidos_faturados_mes'])} |",
        f"| Ticket médio | {moeda(painel['ticket_medio_mes'])} |",
        f"| Estoque a preço de custo | {moeda(painel['valor_estoque'])} |",
        f"| Unidades em estoque | {numero(painel['unidades_em_estoque'])} |",
        f"| Produtos abaixo do mínimo | {numero(painel['produtos_abaixo_minimo'])} |",
        "",
        "### Pedidos por etapa",
        "",
        "| Etapa | Pedidos |",
        "|---|---:|",
        *[f"| {STATUS[s]} | {numero(n)} |" for s, n in painel["pedidos_por_status"].items()],
        "",
        "### Mais vendidos em 30 dias",
        "",
        "| Produto | Unidades | Receita | Margem |",
        "|---|---:|---:|---:|",
        *[
            f"| {p['rotulo']} | {numero(p['quantidade'])} | {moeda(p['receita'])} | {decimal_br(p['margem_percentual'] or 0)}% |"
            for p in painel["top_produtos"]
        ],
        "",
        "### Reposição sugerida",
        "",
    ]
    urgentes = [i for i in giro["itens"] if i["situacao"] in SITUACAO][:8]
    if urgentes:
        linhas += [
            "| Produto | Situação | Disponível | Cobertura | Comprar |",
            "|---|---|---:|---:|---:|",
            *[
                f"| {i['produto']} | {SITUACAO[i['situacao']]} | {numero(i['disponivel'])} | "
                f"{cobertura(i['cobertura_dias'])} | {numero(i['sugestao_compra'])} |"
                for i in urgentes
            ],
        ]
    else:
        linhas.append("Nenhum produto precisa de reposição urgente.")

    total_testes = testes["passaram"] + testes["falharam"] + testes["erros"]
    nova = (
        f"| {data} | {testes['passaram']}/{total_testes} | {moeda(painel['receita_mes'])} | "
        f"{numero(painel['pedidos_faturados_mes'])} | {numero(painel['produtos_abaixo_minimo'])} |"
    )
    historico = [linha for linha in ler_historico() if not linha.startswith(f"| {data} |")]
    historico = [nova, *historico][:LIMITE_HISTORICO]
    linhas += [
        "",
        f"## Histórico (últimos {LIMITE_HISTORICO} dias)",
        "",
        "| Data | Testes OK | Faturamento do mês | Pedidos faturados | Abaixo do mínimo |",
        "|---|---:|---:|---:|---:|",
        *historico,
        "",
    ]
    return "\n".join(linhas)


def main() -> int:
    agora = datetime.now(FUSO)
    testes = ler_testes()
    painel, giro = simular_operacao(agora)
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text(montar(agora, testes, painel, giro), encoding="utf-8", newline="\n")
    print(f"Relatório gravado em {ARQUIVO.relative_to(RAIZ).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
