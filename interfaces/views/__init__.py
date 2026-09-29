from .login_view import login_view
from .dashboard_view import dashboard_view
from .alterar_senha_view import alterar_senha_view
from .produtos_view import produtos_view
from .produto_editar_view import produto_editar_view
from .clientes_view import clientes_view
from .cliente_editar_view import cliente_editar_view
from .vendas_view import vendas_view
from .extrato_cliente_view import extrato_cliente_view
from .vendas_editar_view import venda_editar_view, venda_cancelar_view
from .relatorio_view import relatorio_view
from .extrato_pdf_view import extrato_pdf_view
from .relatorios_export_views import exportar_pdf_modular_view, exportar_excel_modular_view
from .relatorios_analises_views import (
    relatorios_vendas_view, relatorios_produtos_view, relatorios_clientes_view, relatorios_alteracoes_view,
)
from .configuracoes_view import configuracoes_view, marca_enviar_view, marca_remover_view, tema_view
from .planos_view import planos_view, cobranca_view, cobranca_situacao_view
from .lembrete_view import lembrete_view
from .gastos_view import excluir_gasto_view, gastos_view, registrar_gasto_view
from .backup_view import backup_agendado_view
