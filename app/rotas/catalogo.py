from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import func, or_, select

from app.dependencias import Gestor, Operacao, Sessao
from app.erros import Conflito, NaoEncontrado
from app.esquemas.catalogo import (
    CategoriaEntrada,
    CategoriaSaida,
    FornecedorEntrada,
    FornecedorSaida,
    ProdutoAtualizar,
    ProdutoEntrada,
    ProdutoSaida,
)
from app.esquemas.comum import Pagina
from app.esquemas.estoque import MovimentacaoSaida, SaldoSaida
from app.modelos import Categoria, Fornecedor, MovimentacaoEstoque, Produto, SaldoEstoque
from app.servicos import auditoria
from app.servicos.relatorios import para_csv
from app.utils.documentos import so_digitos
from app.utils.paginacao import ParametrosPagina, ordenar, paginar, termo_like

categorias = APIRouter(prefix="/categorias", tags=["Catálogo"])
fornecedores = APIRouter(prefix="/fornecedores", tags=["Catálogo"])
produtos = APIRouter(prefix="/produtos", tags=["Catálogo"])

Busca = Annotated[str | None, Query(max_length=80, description="Texto livre")]


def _obter(sessao, modelo, ident: int, nome: str):
    obj = sessao.get(modelo, ident)
    if obj is None:
        raise NaoEncontrado(f"{nome} {ident} não encontrado.")
    return obj


@categorias.get("", response_model=list[CategoriaSaida])
def listar_categorias(_: Operacao, sessao: Sessao, ativo: bool | None = None):
    consulta = select(Categoria).order_by(Categoria.nome)
    if ativo is not None:
        consulta = consulta.where(Categoria.ativo.is_(ativo))
    return sessao.scalars(consulta).all()


@categorias.post("", response_model=CategoriaSaida, status_code=status.HTTP_201_CREATED)
def criar_categoria(dados: CategoriaEntrada, usuario: Gestor, sessao: Sessao):
    categoria = Categoria(**dados.model_dump())
    sessao.add(categoria)
    sessao.flush()
    auditoria.registrar(sessao, usuario, "categoria_criada", "categoria", categoria.id, {"nome": categoria.nome})
    sessao.commit()
    return categoria


@categorias.put("/{categoria_id}", response_model=CategoriaSaida)
def atualizar_categoria(categoria_id: int, dados: CategoriaEntrada, usuario: Gestor, sessao: Sessao):
    categoria = _obter(sessao, Categoria, categoria_id, "Categoria")
    for campo, valor in dados.model_dump().items():
        setattr(categoria, campo, valor)
    auditoria.registrar(sessao, usuario, "categoria_alterada", "categoria", categoria.id)
    sessao.commit()
    return categoria


@fornecedores.get("", response_model=Pagina[FornecedorSaida])
def listar_fornecedores(_: Operacao, sessao: Sessao, pag: ParametrosPagina, q: Busca = None, ativo: bool | None = None):
    consulta = select(Fornecedor).order_by(Fornecedor.razao_social)
    if q:
        termo = termo_like(q)
        filtros = [Fornecedor.razao_social.ilike(termo, escape="\\"), Fornecedor.nome_fantasia.ilike(termo, escape="\\")]
        if so_digitos(q):
            filtros.append(Fornecedor.cnpj.like(f"%{so_digitos(q)}%"))
        consulta = consulta.where(or_(*filtros))
    if ativo is not None:
        consulta = consulta.where(Fornecedor.ativo.is_(ativo))
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([FornecedorSaida.model_validate(f) for f in itens], total, pag.pagina, pag.por_pagina)


@fornecedores.get("/{fornecedor_id}", response_model=FornecedorSaida)
def obter_fornecedor(fornecedor_id: int, _: Operacao, sessao: Sessao):
    return FornecedorSaida.model_validate(_obter(sessao, Fornecedor, fornecedor_id, "Fornecedor"))


@fornecedores.post("", response_model=FornecedorSaida, status_code=status.HTTP_201_CREATED)
def criar_fornecedor(dados: FornecedorEntrada, usuario: Gestor, sessao: Sessao):
    if sessao.scalars(select(Fornecedor.id).where(Fornecedor.cnpj == dados.cnpj)).first():
        raise Conflito("Já existe um fornecedor com esse CNPJ.")
    fornecedor = Fornecedor(**dados.model_dump())
    sessao.add(fornecedor)
    sessao.flush()
    auditoria.registrar(sessao, usuario, "fornecedor_criado", "fornecedor", fornecedor.id)
    sessao.commit()
    return FornecedorSaida.model_validate(fornecedor)


@fornecedores.put("/{fornecedor_id}", response_model=FornecedorSaida)
def atualizar_fornecedor(fornecedor_id: int, dados: FornecedorEntrada, usuario: Gestor, sessao: Sessao):
    fornecedor = _obter(sessao, Fornecedor, fornecedor_id, "Fornecedor")
    for campo, valor in dados.model_dump().items():
        setattr(fornecedor, campo, valor)
    auditoria.registrar(sessao, usuario, "fornecedor_alterado", "fornecedor", fornecedor.id)
    sessao.commit()
    return FornecedorSaida.model_validate(fornecedor)


def _disponivel_subconsulta():
    return (
        select(
            SaldoEstoque.produto_id.label("pid"),
            func.sum(SaldoEstoque.quantidade - SaldoEstoque.reservado).label("disp"),
        )
        .group_by(SaldoEstoque.produto_id)
        .subquery()
    )


ORDENACAO_PRODUTOS = {
    "nome": Produto.nome,
    "sku": Produto.sku,
    "preco": Produto.preco_venda,
    "atualizado": Produto.atualizado_em,
}


def _consulta_produtos(q, categoria_id, fornecedor_id, ativo, abaixo_minimo, ordem):
    consulta = select(Produto)
    if q:
        termo = termo_like(q)
        filtros = [Produto.nome.ilike(termo, escape="\\"), Produto.sku.ilike(termo, escape="\\")]
        if len(so_digitos(q)) >= 8:
            filtros.append(Produto.codigo_barras == so_digitos(q))
        consulta = consulta.where(or_(*filtros))
    if categoria_id:
        consulta = consulta.where(Produto.categoria_id == categoria_id)
    if fornecedor_id:
        consulta = consulta.where(Produto.fornecedor_id == fornecedor_id)
    if ativo is not None:
        consulta = consulta.where(Produto.ativo.is_(ativo))
    if abaixo_minimo:
        disp = _disponivel_subconsulta()
        consulta = consulta.outerjoin(disp, disp.c.pid == Produto.id).where(
            func.coalesce(disp.c.disp, 0) < Produto.estoque_minimo
        )
    return ordenar(consulta, ordem, ORDENACAO_PRODUTOS, "nome").order_by(Produto.id)


@produtos.get("", response_model=Pagina[ProdutoSaida])
def listar_produtos(
    _: Operacao,
    sessao: Sessao,
    pag: ParametrosPagina,
    q: Busca = None,
    categoria_id: int | None = None,
    fornecedor_id: int | None = None,
    ativo: bool | None = None,
    abaixo_minimo: bool = False,
    ordem: Annotated[str | None, Query(description="nome, sku, preco, atualizado (prefixe com - para decrescente)")] = None,
):
    consulta = _consulta_produtos(q, categoria_id, fornecedor_id, ativo, abaixo_minimo, ordem)
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([ProdutoSaida.de(p) for p in itens], total, pag.pagina, pag.por_pagina)


@produtos.get("/exportar", summary="Exportar a lista filtrada de produtos em CSV")
def exportar_produtos(
    _: Operacao,
    sessao: Sessao,
    q: Busca = None,
    categoria_id: int | None = None,
    ativo: bool | None = None,
    abaixo_minimo: bool = False,
    formato: Literal["csv"] = "csv",
):
    consulta = _consulta_produtos(q, categoria_id, None, ativo, abaixo_minimo, None)
    linhas = [ProdutoSaida.de(p).model_dump(mode="json") for p in sessao.scalars(consulta.limit(20_000)).unique()]
    conteudo = para_csv(
        linhas,
        [
            ("sku", "SKU"),
            ("nome", "Produto"),
            ("categoria", "Categoria"),
            ("fornecedor", "Fornecedor"),
            ("unidade", "Unidade"),
            ("preco_venda", "Preço de venda"),
            ("custo_medio", "Custo médio"),
            ("margem_percentual", "Margem %"),
            ("estoque_total", "Estoque"),
            ("reservado_total", "Reservado"),
            ("disponivel_total", "Disponível"),
            ("estoque_minimo", "Mínimo"),
        ],
    )
    return Response(
        conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="produtos.csv"'},
    )


@produtos.get("/{produto_id}", response_model=ProdutoSaida)
def obter_produto(produto_id: int, _: Operacao, sessao: Sessao):
    return ProdutoSaida.de(_obter(sessao, Produto, produto_id, "Produto"))


@produtos.post("", response_model=ProdutoSaida, status_code=status.HTTP_201_CREATED)
def criar_produto(dados: ProdutoEntrada, usuario: Gestor, sessao: Sessao):
    _obter(sessao, Categoria, dados.categoria_id, "Categoria")
    if dados.fornecedor_id:
        _obter(sessao, Fornecedor, dados.fornecedor_id, "Fornecedor")
    if sessao.scalars(select(Produto.id).where(Produto.sku == dados.sku)).first():
        raise Conflito(f"Já existe um produto com o SKU {dados.sku}.")
    produto = Produto(**dados.model_dump())
    sessao.add(produto)
    sessao.flush()
    auditoria.registrar(sessao, usuario, "produto_criado", "produto", produto.id, {"sku": produto.sku})
    sessao.commit()
    sessao.refresh(produto)
    return ProdutoSaida.de(produto)


@produtos.patch("/{produto_id}", response_model=ProdutoSaida)
def atualizar_produto(produto_id: int, dados: ProdutoAtualizar, usuario: Gestor, sessao: Sessao):
    produto = _obter(sessao, Produto, produto_id, "Produto")
    campos = dados.model_dump(exclude_unset=True)
    versao = campos.pop("versao", None)
    if versao is not None and versao != produto.versao:
        raise Conflito(
            "Este produto foi alterado por outra pessoa depois que você abriu. Recarregue para ver a versão atual.",
            {"versao_atual": produto.versao},
            codigo="concorrencia",
        )
    if campos.get("categoria_id"):
        _obter(sessao, Categoria, campos["categoria_id"], "Categoria")
    if campos.get("fornecedor_id"):
        _obter(sessao, Fornecedor, campos["fornecedor_id"], "Fornecedor")
    antes = {c: getattr(produto, c) for c in campos}
    for campo, valor in campos.items():
        setattr(produto, campo, valor)
    mudancas = auditoria.diferencas(antes, campos)
    if mudancas:
        auditoria.registrar(sessao, usuario, "produto_alterado", "produto", produto.id, mudancas)
    sessao.commit()
    sessao.refresh(produto)
    return ProdutoSaida.de(produto)


@produtos.get("/{produto_id}/saldos", response_model=list[SaldoSaida])
def saldos_do_produto(produto_id: int, _: Operacao, sessao: Sessao):
    produto = _obter(sessao, Produto, produto_id, "Produto")
    return [SaldoSaida.de(s) for s in sorted(produto.saldos, key=lambda s: s.deposito.codigo)]


@produtos.get("/{produto_id}/movimentacoes", response_model=Pagina[MovimentacaoSaida])
def movimentacoes_do_produto(produto_id: int, _: Operacao, sessao: Sessao, pag: ParametrosPagina):
    _obter(sessao, Produto, produto_id, "Produto")
    consulta = (
        select(MovimentacaoEstoque)
        .where(MovimentacaoEstoque.produto_id == produto_id)
        .order_by(MovimentacaoEstoque.criado_em.desc(), MovimentacaoEstoque.id.desc())
    )
    itens, total = paginar(sessao, consulta, pag)
    return Pagina.montar([MovimentacaoSaida.de(m) for m in itens], total, pag.pagina, pag.por_pagina)
