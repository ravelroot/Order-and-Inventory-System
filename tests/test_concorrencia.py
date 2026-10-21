import threading

import pytest

from app.erros import EstoqueInsuficiente
from app.esquemas.pedidos import ItemPedidoEntrada, PedidoCriar
from app.modelos import SaldoEstoque
from app.modelos.enums import Papel
from app.servicos import estoque
from app.servicos import pedidos as servico
from app.servicos.estoque import Contexto
from tests.conftest import FabricaSessao

pytestmark = pytest.mark.postgres


def _preparar(fabrica, sessao, unidades: int, pedidos: int):
    vendedor = fabrica.usuario(Papel.GERENTE)
    categoria = fabrica.categoria()
    deposito = fabrica.deposito()
    produto = fabrica.produto(categoria)
    cliente = fabrica.cliente()
    estoque.entrada(sessao, produto.id, deposito.id, unidades, Contexto(vendedor))
    sessao.commit()
    ids = []
    for _ in range(pedidos):
        dados = PedidoCriar(
            cliente_id=cliente.id, deposito_id=deposito.id, itens=[ItemPedidoEntrada(produto_id=produto.id, quantidade=1)]
        )
        pedido, _ = servico.criar(sessao, dados, vendedor)
        ids.append(pedido.id)
    sessao.commit()
    return vendedor.id, produto.id, deposito.id, ids


def test_confirmacoes_simultaneas_nunca_vendem_alem_do_estoque(fabrica, sessao):
    unidades, concorrentes = 5, 20
    vendedor_id, produto_id, deposito_id, pedidos = _preparar(fabrica, sessao, unidades, concorrentes)
    barreira = threading.Barrier(concorrentes)
    resultados: list[str] = []
    trava = threading.Lock()

    def confirmar(pedido_id: int):
        s = FabricaSessao()
        try:
            from app.modelos import Usuario

            usuario = s.get(Usuario, vendedor_id)
            pedido = servico.obter_pedido(s, pedido_id, travar=True)
            barreira.wait(timeout=10)
            servico.transicionar(s, pedido, "confirmar", usuario)
            s.commit()
            resultado = "ok"
        except EstoqueInsuficiente:
            s.rollback()
            resultado = "sem_estoque"
        finally:
            s.close()
        with trava:
            resultados.append(resultado)

    threads = [threading.Thread(target=confirmar, args=(pid,)) for pid in pedidos]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert resultados.count("ok") == unidades
    assert resultados.count("sem_estoque") == concorrentes - unidades
    with FabricaSessao() as s:
        saldo = s.get(SaldoEstoque, (produto_id, deposito_id))
        assert saldo.reservado == unidades
        assert saldo.quantidade == unidades
