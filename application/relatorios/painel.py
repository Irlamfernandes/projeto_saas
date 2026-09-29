"""O painel do Início: faturamento por período e indicadores comparados, numa única consulta às vendas."""
from dataclasses import dataclass
from decimal import Decimal
from application.relatorios.indicadores import Indicadores, indicadores_do_painel, somas_para_comparar
from application.relatorios.periodos import inicios_dos_periodos
from application.relatorios.selectors import Contexto, soma_das_vendas, somas_desde
from application.tenancy import filtrar_por_loja
from infrastructure.models import Cliente, Produto, Venda

LIMITE_ESTOQUE_BAIXO_PADRAO = 5


@dataclass(frozen=True)
class Painel(Contexto):
    total_produtos: int
    total_clientes: int
    total_geral: Decimal
    vendas_hoje: Decimal
    vendas_semana: Decimal
    vendas_quinzena: Decimal
    vendas_mes: Decimal
    vendas_bimestre: Decimal
    vendas_trimestre: Decimal
    vendas_ano: Decimal
    produtos_baixo_estoque: object
    indicadores: Indicadores


def montar_painel(user, limite_estoque=LIMITE_ESTOQUE_BAIXO_PADRAO, agora=None):
    produtos = filtrar_por_loja(Produto.objects.all(), user)
    somas = filtrar_por_loja(Venda.objects.all(), user).aggregate(
        total=soma_das_vendas(), **somas_desde(inicios_dos_periodos(agora)), **somas_para_comparar(agora),
    )

    return Painel(
        total_produtos=produtos.count(),
        total_clientes=filtrar_por_loja(Cliente.objects.all(), user).count(),
        total_geral=somas['total'],
        vendas_hoje=somas['hoje'],
        vendas_semana=somas['semana'],
        vendas_quinzena=somas['quinzena'],
        vendas_mes=somas['mes'],
        vendas_bimestre=somas['bimestre'],
        vendas_trimestre=somas['trimestre'],
        vendas_ano=somas['ano'],
        produtos_baixo_estoque=(
            produtos.filter(controla_estoque=True, quantidade_estoque__lte=limite_estoque).order_by('quantidade_estoque')
        ),
        indicadores=indicadores_do_painel(user, somas, agora),
    )
