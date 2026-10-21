import argparse
import math
import os
import random
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PASTA_DADOS, obter_config
from app.database import Base, SessaoLocal, agora_utc, engine
from app.erros import EstoqueInsuficiente, RegraViolada
from app.esquemas.pedidos import CompraCriar, ItemCompraEntrada, ItemPedidoEntrada, PedidoCriar
from app.modelos import Categoria, Cliente, Deposito, Fornecedor, PedidoVenda, Produto, SaldoEstoque, Usuario
from app.modelos.enums import Papel, StatusPedido, TipoPessoa, Unidade
from app.seguranca import gerar_hash_senha, gerar_senha_aleatoria
from app.servicos import compras, pedidos
from scripts.dados_ficticios import CATALOGO, CORES, DEPOSITOS, VARIANTES, GeradorFicticio, sem_acento

FUSO = ZoneInfo("America/Sao_Paulo")

USUARIOS_DEMO = [
    ("admin", "Administração (demo)", Papel.ADMIN),
    ("gerente.demo", "Gerência (demo)", Papel.GERENTE),
    ("vendas1.demo", "Vendas 1 (demo)", Papel.VENDEDOR),
    ("vendas2.demo", "Vendas 2 (demo)", Papel.VENDEDOR),
    ("vendas3.demo", "Vendas 3 (demo)", Papel.VENDEDOR),
    ("estoque.demo", "Estoque (demo)", Papel.ESTOQUISTA),
]


class Populador:
    def __init__(self, sessao: Session, semente: int, meses: int, total_pedidos: int, total_clientes: int, total_produtos: int):
        self.s = sessao
        self.g = GeradorFicticio(semente)
        self.r = random.Random(semente + 1)
        self.agora = agora_utc()
        self.inicio = self.agora - timedelta(days=30 * meses)
        self.total_pedidos = total_pedidos
        self.total_clientes = total_clientes
        self.total_produtos = total_produtos
        self.compras_feitas = 0

    def usuarios(self, senha: str) -> dict[str, Usuario]:
        criados = {}
        hash_senha = gerar_hash_senha(senha)
        for login, nome, papel in USUARIOS_DEMO:
            usuario = self.s.scalars(select(Usuario).where(Usuario.usuario == login)).first()
            if usuario is None:
                usuario = Usuario(usuario=login, nome=nome, papel=papel, senha_hash=hash_senha, trocar_senha=False)
                self.s.add(usuario)
            criados[login] = usuario
        self.s.flush()
        return criados

    def estrutura(self) -> None:
        self.depositos = []
        for codigo, nome, cidade, uf in DEPOSITOS:
            deposito = Deposito(codigo=codigo, nome=nome, cidade=cidade, uf=uf)
            self.s.add(deposito)
            self.depositos.append(deposito)

        self.fornecedores = []
        for _ in range(12):
            razao, fantasia = self.g.nome_empresa()
            end = self.g.endereco()
            fornecedor = Fornecedor(
                razao_social=razao,
                nome_fantasia=fantasia,
                cnpj=self.g.cnpj(),
                email=self.g.email(fantasia),
                telefone=end["telefone"],
                cidade=end["cidade"],
                uf=end["uf"],
                prazo_entrega_dias=self.r.choice([3, 5, 7, 10, 15]),
            )
            self.s.add(fornecedor)
            self.fornecedores.append(fornecedor)

        self.produtos = []
        self.popularidade = {}
        modelos = [(cat, item) for cat, itens in CATALOGO.items() for item in itens]
        categorias = {}
        for nome_cat in CATALOGO:
            categoria = Categoria(nome=nome_cat, descricao=f"Produtos de {nome_cat.lower()}")
            self.s.add(categoria)
            categorias[nome_cat] = categoria
        self.s.flush()

        usados: set[str] = set()
        while len(self.produtos) < self.total_produtos:
            nome_cat, (nome_base, faixa, unidade) = modelos[len(self.produtos) % len(modelos)]
            nome = nome_base
            if nome in usados:
                nome = f"{nome_base}{self.r.choice(VARIANTES[1:])}{self.r.choice(CORES)}"
                if nome in usados:
                    continue
            usados.add(nome)
            prefixo = sem_acento(nome_cat)[:3].upper()
            preco = self.g.preco(faixa)
            custo = (preco * Decimal(self.r.uniform(0.45, 0.68))).quantize(Decimal("0.01"))
            produto = Produto(
                sku=f"{prefixo}-{len(self.produtos) + 1:04d}",
                codigo_barras=self.g.ean13(),
                nome=nome,
                descricao="Item de demonstração, com dados fictícios.",
                categoria_id=categorias[nome_cat].id,
                fornecedor_id=self.r.choice(self.fornecedores).id,
                unidade=Unidade(unidade),
                preco_venda=preco,
                custo_medio=Decimal("0"),
                estoque_minimo=self.r.choice([5, 10, 10, 15, 20, 30]),
            )
            produto._custo_referencia = custo
            self.s.add(produto)
            self.produtos.append(produto)
            self.popularidade[len(self.produtos) - 1] = self.r.lognormvariate(0, 0.9)
        self.s.flush()

        self.clientes = []
        for i in range(self.total_clientes):
            end = self.g.endereco()
            if i % 5 == 4:
                razao, fantasia = self.g.nome_empresa()
                cliente = Cliente(
                    tipo_pessoa=TipoPessoa.JURIDICA,
                    nome=razao,
                    documento=self.g.cnpj(),
                    email=self.g.email(fantasia),
                    limite_credito=Decimal(self.r.choice([0, 20000, 50000, 100000])),
                    **end,
                )
            else:
                nome = self.g.nome_pessoa()
                cliente = Cliente(
                    tipo_pessoa=TipoPessoa.FISICA,
                    nome=nome,
                    documento=self.g.cpf(),
                    email=self.g.email(nome),
                    **end,
                )
            cliente.criado_em = self.inicio - timedelta(days=self.r.randint(1, 400))
            self.s.add(cliente)
            self.clientes.append(cliente)
        self.peso_clientes = [self.r.paretovariate(1.4) for _ in self.clientes]
        self.s.flush()

    def _comprar(self, deposito: Deposito, itens: dict[int, int], quando: datetime) -> None:
        por_fornecedor: dict[int, list[ItemCompraEntrada]] = {}
        for produto_id, quantidade in itens.items():
            produto = self.s.get(Produto, produto_id)
            custo = getattr(produto, "_custo_referencia", None) or produto.custo_medio or produto.preco_venda * Decimal("0.55")
            custo = (Decimal(custo) * Decimal(self.r.uniform(0.95, 1.06))).quantize(Decimal("0.01"))
            por_fornecedor.setdefault(produto.fornecedor_id, []).append(
                ItemCompraEntrada(produto_id=produto_id, quantidade=quantidade, custo_unitario=custo)
            )
        for fornecedor_id, entradas in por_fornecedor.items():
            dados = CompraCriar(
                fornecedor_id=fornecedor_id,
                deposito_id=deposito.id,
                itens=entradas,
                previsao_entrega=(quando + timedelta(days=5)).date(),
            )
            compra = compras.criar(self.s, dados, self.u["gerente.demo"], agora=quando - timedelta(days=5))
            compras.enviar(compra, agora=quando - timedelta(days=5) + timedelta(hours=2))
            compras.receber(self.s, compra, self.u["estoque.demo"], agora=quando)
            self.compras_feitas += 1

    def carga_inicial(self) -> None:
        quando = self.inicio - timedelta(days=1)
        for i, deposito in enumerate(self.depositos):
            fator = [1.0, 0.6, 0.45][i]
            itens = {
                p.id: max(8, int(self.popularidade[idx] * 14 * fator) + self.r.randint(4, 18))
                for idx, p in enumerate(self.produtos)
            }
            self._comprar(deposito, itens, quando)
        self.s.commit()

    def _repor_se_preciso(self, deposito: Deposito, necessidade: dict[int, int], quando: datetime) -> None:
        faltando = {}
        for produto_id, quantidade in necessidade.items():
            saldo = self.s.get(SaldoEstoque, (produto_id, deposito.id))
            disponivel = saldo.disponivel if saldo else 0
            if disponivel < quantidade:
                faltando[produto_id] = max(quantidade * 2, quantidade + 6)
        if faltando:
            self._comprar(deposito, faltando, quando - timedelta(hours=3))

    def reposicao_periodica(self, quando: datetime) -> None:
        for deposito, fator in zip(self.depositos, (1.6, 0.8, 0.6), strict=True):
            saldos = self.s.scalars(select(SaldoEstoque).where(SaldoEstoque.deposito_id == deposito.id)).all()
            itens = {}
            for saldo in saldos:
                alvo = int(saldo.produto.estoque_minimo * fator) + self.r.randint(0, 8)
                if saldo.disponivel < saldo.produto.estoque_minimo * fator * 0.6 and self.r.random() < 0.6:
                    itens[saldo.produto_id] = max(alvo - saldo.disponivel, 5)
            if itens:
                self._comprar(deposito, itens, quando)
        self.s.commit()

    def _momentos_dos_pedidos(self) -> list[datetime]:
        dias = (self.agora - self.inicio).days
        pesos = []
        for d in range(dias + 1):
            dia = (self.inicio + timedelta(days=d)).astimezone(FUSO).date()
            semana = [1.0, 1.1, 1.1, 1.05, 1.2, 0.55, 0.25][dia.weekday()]
            tendencia = 0.75 + 0.5 * d / max(dias, 1)
            sazonal = 1 + 0.15 * math.sin(d / 9)
            pesos.append(semana * tendencia * sazonal)
        escolhidos = self.r.choices(range(dias + 1), weights=pesos, k=self.total_pedidos)
        momentos = []
        for d in escolhidos:
            dia = (self.inicio + timedelta(days=d)).astimezone(FUSO).date()
            hora = time(self.r.randint(8, 18), self.r.randint(0, 59), self.r.randint(0, 59))
            momento = datetime.combine(dia, hora, FUSO).astimezone(ZoneInfo("UTC"))
            if momento < self.agora - timedelta(minutes=30):
                momentos.append(momento)
        return sorted(momentos)

    def pedidos(self) -> dict[str, int]:
        vendedores = [self.u["vendas1.demo"], self.u["vendas2.demo"], self.u["vendas3.demo"], self.u["gerente.demo"]]
        pesos_vendedor = [0.36, 0.30, 0.24, 0.10]
        pesos_deposito = [0.55, 0.27, 0.18]
        pesos_produto = [self.popularidade[i] for i in range(len(self.produtos))]
        contagem: dict[str, int] = {}
        proxima_reposicao = self.inicio + timedelta(days=14)

        for n, momento in enumerate(self._momentos_dos_pedidos(), start=1):
            if momento >= proxima_reposicao:
                self.reposicao_periodica(proxima_reposicao)
                proxima_reposicao += timedelta(days=14)

            vendedor = self.r.choices(vendedores, weights=pesos_vendedor)[0]
            deposito = self.r.choices(self.depositos, weights=pesos_deposito)[0]
            cliente = self.r.choices(self.clientes, weights=self.peso_clientes)[0]
            quantos = self.r.choices([1, 2, 3, 4, 5], weights=[30, 30, 20, 12, 8])[0]
            indices = set()
            while len(indices) < quantos:
                indices.add(self.r.choices(range(len(self.produtos)), weights=pesos_produto)[0])
            itens = []
            for idx in sorted(indices):
                produto = self.produtos[idx]
                quantidade = self.r.choices([1, 1, 2, 2, 3, 4, 5, 8, 10], k=1)[0]
                if cliente.tipo_pessoa == TipoPessoa.JURIDICA:
                    quantidade *= self.r.choice([2, 2, 3])
                limite = 10 if vendedor.papel == Papel.VENDEDOR else 20
                desconto = Decimal(self.r.choice([0, 0, 0, 0, 3, 5, 5, limite]))
                itens.append(ItemPedidoEntrada(produto_id=produto.id, quantidade=quantidade, desconto_percentual=desconto))
            frete = Decimal(self.r.choice(["0", "0", "19.90", "29.90", "49.90"]))
            dados = PedidoCriar(cliente_id=cliente.id, deposito_id=deposito.id, itens=itens, frete=frete)
            pedido, _ = pedidos.criar(self.s, dados, vendedor, agora=momento)
            status = self._avancar(pedido, vendedor, deposito, momento)
            contagem[status] = contagem.get(status, 0) + 1
            if n % 50 == 0:
                self.s.commit()
                print(f"  {n} pedidos...", flush=True)
        self.s.commit()
        return contagem

    def _avancar(self, pedido: PedidoVenda, vendedor: Usuario, deposito: Deposito, criado: datetime) -> str:
        estoquista, gerente = self.u["estoque.demo"], self.u["gerente.demo"]
        idade = (self.agora - criado).total_seconds() / 86400
        cancelar_em = None
        sorte = self.r.random()
        if sorte < 0.04:
            cancelar_em = "RASCUNHO"
        elif sorte < 0.08:
            cancelar_em = "CONFIRMADO"
        elif sorte < 0.095:
            cancelar_em = "FATURADO"

        passos = [
            ("confirmar", vendedor, (0.05, 4)),
            ("separar", estoquista, (2, 20)),
            ("faturar", estoquista, (1, 20)),
            ("enviar", estoquista, (2, 24)),
            ("entregar", estoquista, (24, 24 * 6)),
        ]
        parar_em = self.r.randint(0, len(passos)) if idade < 4 else None
        momento = criado
        for indice, (acao, usuario, (min_h, max_h)) in enumerate(passos):
            if parar_em is not None and indice >= parar_em and cancelar_em is None:
                break
            if cancelar_em == pedido.status.value:
                quando = momento + timedelta(hours=self.r.uniform(1, 30))
                if quando < self.agora:
                    quem = gerente if pedido.status == StatusPedido.FATURADO else vendedor
                    motivo = self.r.choice(
                        ["Cliente desistiu da compra", "Pagamento não aprovado", "Prazo de entrega não atendeu", "Devolução"]
                    )
                    pedidos.transicionar(self.s, pedido, "cancelar", quem, motivo=motivo, agora=quando)
                break
            proximo = momento + timedelta(hours=self.r.uniform(min_h, max_h))
            if proximo >= self.agora or (acao == "confirmar" and idade < 0.4 and self.r.random() < 0.5):
                break
            extras = {}
            if acao == "confirmar":
                necessidade = {i.produto_id: i.quantidade for i in pedido.itens}
                self._repor_se_preciso(deposito, necessidade, proximo)
            if acao == "enviar":
                extras["codigo_rastreio"] = f"BR{self.r.randint(100000000, 999999999)}XX"
            try:
                pedidos.transicionar(self.s, pedido, acao, usuario, agora=proximo, **extras)
            except RegraViolada as erro:
                if getattr(erro, "codigo", "") != "limite_credito":
                    raise
                pedidos.transicionar(self.s, pedido, acao, gerente, agora=proximo, **extras)
            except EstoqueInsuficiente:
                break
            momento = proximo
        return pedido.status.value

    def inventario_final(self) -> None:
        from app.modelos.enums import OrigemMovimentacao
        from app.servicos import estoque
        from app.servicos.estoque import Contexto

        quando = self.agora - timedelta(hours=20)
        ctx = Contexto(self.u["estoque.demo"], OrigemMovimentacao.INVENTARIO, motivo="Inventário: avarias e perdas", agora=quando)
        for produto in self.r.sample(self.produtos, 7):
            for deposito in self.depositos:
                saldo = self.s.get(SaldoEstoque, (produto.id, deposito.id))
                if saldo is not None:
                    contada = max(saldo.reservado, self.r.choice([0, 0, 1, 2, 3]))
                    estoque.ajustar(self.s, produto.id, deposito.id, contada, ctx)
        self.s.commit()

    def compras_em_aberto(self) -> None:
        deposito = self.depositos[0]
        saldos = sorted(
            self.s.scalars(select(SaldoEstoque).where(SaldoEstoque.deposito_id == deposito.id)).all(),
            key=lambda s: s.disponivel - s.produto.estoque_minimo,
        )[:9]
        grupos = [saldos[0:3], saldos[3:6], saldos[6:9]]
        for situacao, grupo in zip(("rascunho", "enviado", "parcial"), grupos, strict=True):
            if not grupo:
                continue
            fornecedor_id = grupo[0].produto.fornecedor_id
            entradas = [
                ItemCompraEntrada(
                    produto_id=s.produto_id,
                    quantidade=s.produto.estoque_minimo * 4,
                    custo_unitario=(s.produto.custo_medio or Decimal("10")).quantize(Decimal("0.01")),
                )
                for s in grupo
            ]
            quando = self.agora - timedelta(days=self.r.randint(1, 4))
            dados = CompraCriar(
                fornecedor_id=fornecedor_id,
                deposito_id=deposito.id,
                itens=entradas,
                previsao_entrega=(quando + timedelta(days=7)).date(),
                observacoes="Reposição de itens abaixo do mínimo",
            )
            compra = compras.criar(self.s, dados, self.u["gerente.demo"], agora=quando)
            if situacao in ("enviado", "parcial"):
                compras.enviar(compra, agora=quando + timedelta(hours=3))
            if situacao == "parcial":
                from app.esquemas.pedidos import ItemRecebimento

                item = compra.itens[0]
                compras.receber(
                    self.s,
                    compra,
                    self.u["estoque.demo"],
                    [ItemRecebimento(item_id=item.id, quantidade=item.quantidade // 2)],
                    agora=min(quando + timedelta(days=1), self.agora),
                )
        self.s.commit()


def _senha_demo() -> str:
    return os.environ.get("SENHA_DEMO") or obter_config().senha_demo or gerar_senha_aleatoria()


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o banco com dados fictícios.")
    parser.add_argument("--semente", type=int, default=42, help="Mesma semente = mesmos dados")
    parser.add_argument("--meses", type=int, default=6)
    parser.add_argument("--pedidos", type=int, default=700)
    parser.add_argument("--clientes", type=int, default=160)
    parser.add_argument("--produtos", type=int, default=80)
    parser.add_argument("--limpar", action="store_true", help="Apaga todas as tabelas antes de popular")
    args = parser.parse_args()

    if args.limpar:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    with SessaoLocal() as sessao:
        if sessao.scalars(select(Produto.id).limit(1)).first() is not None:
            print("O banco já tem produtos. Use --limpar para recomeçar do zero.")
            return
        populador = Populador(sessao, args.semente, args.meses, args.pedidos, args.clientes, args.produtos)
        senha = _senha_demo()
        populador.u = populador.usuarios(senha)
        print("Criando depósitos, fornecedores, produtos e clientes fictícios...")
        populador.estrutura()
        print("Carga inicial de estoque...")
        populador.carga_inicial()
        print(f"Gerando {args.pedidos} pedidos ao longo de {args.meses} meses...")
        contagem = populador.pedidos()
        populador.inventario_final()
        populador.compras_em_aberto()

        PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        arquivo = PASTA_DADOS / "credenciais_demo.txt"
        linhas = [f"{login:<14} {papel.value:<11} senha: {senha}" for login, _, papel in USUARIOS_DEMO]
        arquivo.write_text(
            "Usuários de demonstração (arquivo local, fora do Git)\n\n" + "\n".join(linhas) + "\n", encoding="utf-8"
        )
        print("\nPronto!")
        print(f"  Pedidos por status: {dict(sorted(contagem.items()))}")
        print(f"  Pedidos de compra gerados: {populador.compras_feitas}")
        print(f"  Credenciais de demonstração salvas em: dados/{arquivo.name}")
        print("\n".join("  " + linha for linha in linhas))
        print(f"\nPeríodo simulado: {populador.inicio.date()} a {date.today()}")


if __name__ == "__main__":
    main()
