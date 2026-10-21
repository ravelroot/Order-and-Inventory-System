from enum import StrEnum


class Papel(StrEnum):
    ADMIN = "admin"
    GERENTE = "gerente"
    VENDEDOR = "vendedor"
    ESTOQUISTA = "estoquista"


class TipoPessoa(StrEnum):
    FISICA = "F"
    JURIDICA = "J"


class TipoMovimentacao(StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    AJUSTE_POSITIVO = "AJUSTE_POSITIVO"
    AJUSTE_NEGATIVO = "AJUSTE_NEGATIVO"
    TRANSFERENCIA_SAIDA = "TRANSFERENCIA_SAIDA"
    TRANSFERENCIA_ENTRADA = "TRANSFERENCIA_ENTRADA"
    RESERVA = "RESERVA"
    LIBERACAO_RESERVA = "LIBERACAO_RESERVA"
    ESTORNO = "ESTORNO"


class OrigemMovimentacao(StrEnum):
    MANUAL = "MANUAL"
    PEDIDO_VENDA = "PEDIDO_VENDA"
    PEDIDO_COMPRA = "PEDIDO_COMPRA"
    TRANSFERENCIA = "TRANSFERENCIA"
    INVENTARIO = "INVENTARIO"


class StatusPedido(StrEnum):
    RASCUNHO = "RASCUNHO"
    CONFIRMADO = "CONFIRMADO"
    SEPARADO = "SEPARADO"
    FATURADO = "FATURADO"
    ENVIADO = "ENVIADO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


STATUS_FATURADOS = (StatusPedido.FATURADO, StatusPedido.ENVIADO, StatusPedido.ENTREGUE)
STATUS_ABERTOS = (StatusPedido.RASCUNHO, StatusPedido.CONFIRMADO, StatusPedido.SEPARADO)


class StatusCompra(StrEnum):
    RASCUNHO = "RASCUNHO"
    ENVIADO = "ENVIADO"
    RECEBIDO_PARCIAL = "RECEBIDO_PARCIAL"
    RECEBIDO = "RECEBIDO"
    CANCELADO = "CANCELADO"


class Unidade(StrEnum):
    UN = "UN"
    CX = "CX"
    PC = "PC"
    KIT = "KIT"
    PAR = "PAR"
    RL = "RL"
