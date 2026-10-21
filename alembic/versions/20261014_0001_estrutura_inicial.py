from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.database import DataHoraUTC
from app.database import DecimalFixo

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('categoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=80), nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_categoria')),
    sa.UniqueConstraint('nome', name=op.f('uq_categoria_nome'))
    )
    op.create_table('cliente',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tipo_pessoa', sa.Enum('F', 'J', name='tipo_pessoa', native_enum=False, length=24), nullable=False),
    sa.Column('nome', sa.String(length=160), nullable=False),
    sa.Column('documento', sa.String(length=14), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=True),
    sa.Column('telefone', sa.String(length=20), nullable=True),
    sa.Column('cep', sa.String(length=8), nullable=True),
    sa.Column('logradouro', sa.String(length=160), nullable=True),
    sa.Column('numero', sa.String(length=10), nullable=True),
    sa.Column('complemento', sa.String(length=60), nullable=True),
    sa.Column('bairro', sa.String(length=80), nullable=True),
    sa.Column('cidade', sa.String(length=80), nullable=True),
    sa.Column('uf', sa.String(length=2), nullable=True),
    sa.Column('limite_credito', DecimalFixo(2), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cliente')),
    sa.UniqueConstraint('documento', name=op.f('uq_cliente_documento'))
    )
    op.create_index(op.f('ix_cliente_nome'), 'cliente', ['nome'], unique=False)
    op.create_table('deposito',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=12), nullable=False),
    sa.Column('nome', sa.String(length=80), nullable=False),
    sa.Column('cidade', sa.String(length=80), nullable=True),
    sa.Column('uf', sa.String(length=2), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_deposito')),
    sa.UniqueConstraint('codigo', name=op.f('uq_deposito_codigo'))
    )
    op.create_table('fornecedor',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('razao_social', sa.String(length=160), nullable=False),
    sa.Column('nome_fantasia', sa.String(length=120), nullable=True),
    sa.Column('cnpj', sa.String(length=14), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=True),
    sa.Column('telefone', sa.String(length=20), nullable=True),
    sa.Column('cidade', sa.String(length=80), nullable=True),
    sa.Column('uf', sa.String(length=2), nullable=True),
    sa.Column('prazo_entrega_dias', sa.Integer(), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fornecedor')),
    sa.UniqueConstraint('cnpj', name=op.f('uq_fornecedor_cnpj'))
    )
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('usuario', sa.String(length=40), nullable=False),
    sa.Column('email', sa.String(length=160), nullable=True),
    sa.Column('senha_hash', sa.String(length=255), nullable=False),
    sa.Column('papel', sa.Enum('admin', 'gerente', 'vendedor', 'estoquista', name='papel', native_enum=False, length=24), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('versao_token', sa.Integer(), nullable=False),
    sa.Column('trocar_senha', sa.Boolean(), nullable=False),
    sa.Column('ultimo_acesso', DataHoraUTC(), nullable=True),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuario')),
    sa.UniqueConstraint('email', name=op.f('uq_usuario_email')),
    sa.UniqueConstraint('usuario', name=op.f('uq_usuario_usuario'))
    )
    op.create_table('auditoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('acao', sa.String(length=40), nullable=False),
    sa.Column('entidade', sa.String(length=40), nullable=False),
    sa.Column('entidade_id', sa.Integer(), nullable=True),
    sa.Column('detalhes', sa.JSON(), nullable=True),
    sa.Column('origem_hash', sa.String(length=16), nullable=True),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_auditoria_usuario_id_usuario'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auditoria'))
    )
    op.create_index(op.f('ix_auditoria_acao'), 'auditoria', ['acao'], unique=False)
    op.create_index(op.f('ix_auditoria_criado_em'), 'auditoria', ['criado_em'], unique=False)
    op.create_index('ix_auditoria_entidade', 'auditoria', ['entidade', 'entidade_id'], unique=False)
    op.create_table('pedido_compra',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('numero', sa.String(length=20), nullable=True),
    sa.Column('fornecedor_id', sa.Integer(), nullable=False),
    sa.Column('deposito_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('RASCUNHO', 'ENVIADO', 'RECEBIDO_PARCIAL', 'RECEBIDO', 'CANCELADO', name='status_compra', native_enum=False, length=24), nullable=False),
    sa.Column('previsao_entrega', sa.Date(), nullable=True),
    sa.Column('total', DecimalFixo(2), nullable=False),
    sa.Column('observacoes', sa.Text(), nullable=True),
    sa.Column('criado_por_id', sa.Integer(), nullable=True),
    sa.Column('enviado_em', DataHoraUTC(), nullable=True),
    sa.Column('recebido_em', DataHoraUTC(), nullable=True),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['criado_por_id'], ['usuario.id'], name=op.f('fk_pedido_compra_criado_por_id_usuario'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['deposito_id'], ['deposito.id'], name=op.f('fk_pedido_compra_deposito_id_deposito'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['fornecedor_id'], ['fornecedor.id'], name=op.f('fk_pedido_compra_fornecedor_id_fornecedor'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pedido_compra')),
    sa.UniqueConstraint('numero', name=op.f('uq_pedido_compra_numero'))
    )
    op.create_table('pedido_venda',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('numero', sa.String(length=20), nullable=True),
    sa.Column('cliente_id', sa.Integer(), nullable=False),
    sa.Column('deposito_id', sa.Integer(), nullable=False),
    sa.Column('vendedor_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('RASCUNHO', 'CONFIRMADO', 'SEPARADO', 'FATURADO', 'ENVIADO', 'ENTREGUE', 'CANCELADO', name='status_pedido', native_enum=False, length=24), nullable=False),
    sa.Column('subtotal', DecimalFixo(2), nullable=False),
    sa.Column('desconto_total', DecimalFixo(2), nullable=False),
    sa.Column('frete', DecimalFixo(2), nullable=False),
    sa.Column('total', DecimalFixo(2), nullable=False),
    sa.Column('observacoes', sa.Text(), nullable=True),
    sa.Column('codigo_rastreio', sa.String(length=40), nullable=True),
    sa.Column('motivo_cancelamento', sa.String(length=255), nullable=True),
    sa.Column('chave_idempotencia', sa.String(length=80), nullable=True),
    sa.Column('confirmado_em', DataHoraUTC(), nullable=True),
    sa.Column('faturado_em', DataHoraUTC(), nullable=True),
    sa.Column('enviado_em', DataHoraUTC(), nullable=True),
    sa.Column('entregue_em', DataHoraUTC(), nullable=True),
    sa.Column('cancelado_em', DataHoraUTC(), nullable=True),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.CheckConstraint('total >= 0', name=op.f('ck_pedido_venda_total_nao_negativo')),
    sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id'], name=op.f('fk_pedido_venda_cliente_id_cliente'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['deposito_id'], ['deposito.id'], name=op.f('fk_pedido_venda_deposito_id_deposito'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vendedor_id'], ['usuario.id'], name=op.f('fk_pedido_venda_vendedor_id_usuario'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pedido_venda')),
    sa.UniqueConstraint('numero', name=op.f('uq_pedido_venda_numero')),
    sa.UniqueConstraint('vendedor_id', 'chave_idempotencia', name='uq_pedido_venda_idempotencia')
    )
    op.create_index(op.f('ix_pedido_venda_faturado_em'), 'pedido_venda', ['faturado_em'], unique=False)
    op.create_index('ix_pedido_venda_status_data', 'pedido_venda', ['status', 'criado_em'], unique=False)
    op.create_table('produto',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sku', sa.String(length=30), nullable=False),
    sa.Column('codigo_barras', sa.String(length=14), nullable=True),
    sa.Column('nome', sa.String(length=160), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('fornecedor_id', sa.Integer(), nullable=True),
    sa.Column('unidade', sa.Enum('UN', 'CX', 'PC', 'KIT', 'PAR', 'RL', name='unidade', native_enum=False, length=24), nullable=False),
    sa.Column('preco_venda', DecimalFixo(2), nullable=False),
    sa.Column('custo_medio', DecimalFixo(2), nullable=False),
    sa.Column('estoque_minimo', sa.Integer(), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('versao', sa.Integer(), nullable=False),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.CheckConstraint('custo_medio >= 0', name=op.f('ck_produto_custo_nao_negativo')),
    sa.CheckConstraint('estoque_minimo >= 0', name=op.f('ck_produto_minimo_nao_negativo')),
    sa.CheckConstraint('preco_venda >= 0', name=op.f('ck_produto_preco_nao_negativo')),
    sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], name=op.f('fk_produto_categoria_id_categoria'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['fornecedor_id'], ['fornecedor.id'], name=op.f('fk_produto_fornecedor_id_fornecedor'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_produto')),
    sa.UniqueConstraint('codigo_barras', name=op.f('uq_produto_codigo_barras')),
    sa.UniqueConstraint('sku', name=op.f('uq_produto_sku'))
    )
    op.create_index(op.f('ix_produto_nome'), 'produto', ['nome'], unique=False)
    op.create_table('historico_pedido',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pedido_id', sa.Integer(), nullable=False),
    sa.Column('de_status', sa.Enum('RASCUNHO', 'CONFIRMADO', 'SEPARADO', 'FATURADO', 'ENVIADO', 'ENTREGUE', 'CANCELADO', name='status_pedido', native_enum=False, length=24), nullable=True),
    sa.Column('para_status', sa.Enum('RASCUNHO', 'CONFIRMADO', 'SEPARADO', 'FATURADO', 'ENVIADO', 'ENTREGUE', 'CANCELADO', name='status_pedido', native_enum=False, length=24), nullable=False),
    sa.Column('observacao', sa.String(length=255), nullable=True),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedido_venda.id'], name=op.f('fk_historico_pedido_pedido_id_pedido_venda'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_historico_pedido_usuario_id_usuario'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_historico_pedido'))
    )
    op.create_index(op.f('ix_historico_pedido_pedido_id'), 'historico_pedido', ['pedido_id'], unique=False)
    op.create_table('item_pedido_compra',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pedido_id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('quantidade_recebida', sa.Integer(), nullable=False),
    sa.Column('custo_unitario', DecimalFixo(2), nullable=False),
    sa.CheckConstraint('quantidade > 0', name=op.f('ck_item_pedido_compra_quantidade_positiva')),
    sa.CheckConstraint('quantidade_recebida >= 0 AND quantidade_recebida <= quantidade', name=op.f('ck_item_pedido_compra_recebida_valida')),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedido_compra.id'], name=op.f('fk_item_pedido_compra_pedido_id_pedido_compra'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['produto_id'], ['produto.id'], name=op.f('fk_item_pedido_compra_produto_id_produto'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_item_pedido_compra')),
    sa.UniqueConstraint('pedido_id', 'produto_id', name='uq_item_compra_produto')
    )
    op.create_table('item_pedido_venda',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pedido_id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('preco_unitario', DecimalFixo(2), nullable=False),
    sa.Column('desconto_percentual', DecimalFixo(2), nullable=False),
    sa.Column('custo_unitario', DecimalFixo(2), nullable=False),
    sa.Column('total', DecimalFixo(2), nullable=False),
    sa.CheckConstraint('desconto_percentual >= 0 AND desconto_percentual <= 10000', name=op.f('ck_item_pedido_venda_desconto_valido')),
    sa.CheckConstraint('quantidade > 0', name=op.f('ck_item_pedido_venda_quantidade_positiva')),
    sa.ForeignKeyConstraint(['pedido_id'], ['pedido_venda.id'], name=op.f('fk_item_pedido_venda_pedido_id_pedido_venda'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['produto_id'], ['produto.id'], name=op.f('fk_item_pedido_venda_produto_id_produto'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_item_pedido_venda')),
    sa.UniqueConstraint('pedido_id', 'produto_id', name='uq_item_pedido_produto')
    )
    op.create_table('movimentacao_estoque',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('deposito_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.Enum('ENTRADA', 'SAIDA', 'AJUSTE_POSITIVO', 'AJUSTE_NEGATIVO', 'TRANSFERENCIA_SAIDA', 'TRANSFERENCIA_ENTRADA', 'RESERVA', 'LIBERACAO_RESERVA', 'ESTORNO', name='tipo_movimentacao', native_enum=False, length=24), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('saldo_apos', sa.Integer(), nullable=False),
    sa.Column('reservado_apos', sa.Integer(), nullable=False),
    sa.Column('custo_unitario', DecimalFixo(2), nullable=True),
    sa.Column('origem', sa.Enum('MANUAL', 'PEDIDO_VENDA', 'PEDIDO_COMPRA', 'TRANSFERENCIA', 'INVENTARIO', name='origem_movimentacao', native_enum=False, length=24), nullable=False),
    sa.Column('origem_id', sa.Integer(), nullable=True),
    sa.Column('motivo', sa.String(length=255), nullable=True),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('criado_em', DataHoraUTC(), nullable=False),
    sa.CheckConstraint('quantidade > 0', name=op.f('ck_movimentacao_estoque_quantidade_positiva')),
    sa.ForeignKeyConstraint(['deposito_id'], ['deposito.id'], name=op.f('fk_movimentacao_estoque_deposito_id_deposito'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['produto_id'], ['produto.id'], name=op.f('fk_movimentacao_estoque_produto_id_produto'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], name=op.f('fk_movimentacao_estoque_usuario_id_usuario'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_movimentacao_estoque'))
    )
    op.create_index('ix_movimentacao_origem', 'movimentacao_estoque', ['origem', 'origem_id'], unique=False)
    op.create_index('ix_movimentacao_produto_data', 'movimentacao_estoque', ['produto_id', 'criado_em'], unique=False)
    op.create_table('saldo_estoque',
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('deposito_id', sa.Integer(), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('reservado', sa.Integer(), nullable=False),
    sa.Column('atualizado_em', DataHoraUTC(), nullable=False),
    sa.CheckConstraint('quantidade >= 0', name=op.f('ck_saldo_estoque_quantidade_nao_negativa')),
    sa.CheckConstraint('reservado <= quantidade', name=op.f('ck_saldo_estoque_reserva_ate_quantidade')),
    sa.CheckConstraint('reservado >= 0', name=op.f('ck_saldo_estoque_reservado_nao_negativo')),
    sa.ForeignKeyConstraint(['deposito_id'], ['deposito.id'], name=op.f('fk_saldo_estoque_deposito_id_deposito'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['produto_id'], ['produto.id'], name=op.f('fk_saldo_estoque_produto_id_produto'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('produto_id', 'deposito_id', name=op.f('pk_saldo_estoque'))
    )


def downgrade() -> None:
    op.drop_table('saldo_estoque')
    op.drop_index('ix_movimentacao_produto_data', table_name='movimentacao_estoque')
    op.drop_index('ix_movimentacao_origem', table_name='movimentacao_estoque')
    op.drop_table('movimentacao_estoque')
    op.drop_table('item_pedido_venda')
    op.drop_table('item_pedido_compra')
    op.drop_index(op.f('ix_historico_pedido_pedido_id'), table_name='historico_pedido')
    op.drop_table('historico_pedido')
    op.drop_index(op.f('ix_produto_nome'), table_name='produto')
    op.drop_table('produto')
    op.drop_index('ix_pedido_venda_status_data', table_name='pedido_venda')
    op.drop_index(op.f('ix_pedido_venda_faturado_em'), table_name='pedido_venda')
    op.drop_table('pedido_venda')
    op.drop_table('pedido_compra')
    op.drop_index('ix_auditoria_entidade', table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_criado_em'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_acao'), table_name='auditoria')
    op.drop_table('auditoria')
    op.drop_table('usuario')
    op.drop_table('fornecedor')
    op.drop_table('deposito')
    op.drop_index(op.f('ix_cliente_nome'), table_name='cliente')
    op.drop_table('cliente')
    op.drop_table('categoria')
