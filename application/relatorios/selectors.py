from dataclasses import dataclass, fields
from decimal import Decimal
from django.db.models import Avg, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from application.relatorios.periodos import inicios_dos_periodos
from application.tenancy import filtrar_por_loja
from infrastructure.models import Cliente, Produto, Venda

_DINHEIRO = DecimalField(max_digits=14, decimal_places=2)
_ZERO = Value(Decimal('0.00'), output_field=_DINHEIRO)


class Contexto:
    def como_contexto(self):
        """Campos como dict raso, pronto para o contexto do template."""
        return {campo.name: getattr(self, campo.name) for campo in fields(self)}


@dataclass(frozen=True)
class Relatorio(Contexto):
    total_geral_vendas: Decimal
    ticket_medio: Decimal
    vendas_hoje_valor: Decimal
    vendas_semana_valor: Decimal
    vendas_mes_valor: Decimal
    vendas_ano_valor: Decimal
    clientes_devendo: list
    total_fiado_pendente: Decimal
    clientes_credito: list
    total_credito_clientes: Decimal
    estoque_ordenado: list


def faturamento_por_periodo(vendas, inicios):
    """Soma das vendas no total e a partir de cada início informado, numa única consulta."""
    return vendas.aggregate(total=soma_das_vendas(), **somas_desde(inicios))


def somas_desde(inicios):
    """Uma soma das vendas a partir de cada início, para usar num aggregate."""
    return {nome: soma_das_vendas(Q(data_venda__gte=inicio)) for nome, inicio in inicios.items()}


def filtrar_por_intervalo(queryset, inicio=None, fim=None, campo='data_venda'):
    """Filtra por datas (inclusivas) no calendário local. `campo` é o datetime a comparar."""
    if inicio:
        queryset = queryset.filter(**{f'{campo}__date__gte': inicio})
    if fim:
        queryset = queryset.filter(**{f'{campo}__date__lte': fim})
    return queryset


def montar_relatorio(user, inicio=None, fim=None, agora=None):
    vendas = filtrar_por_loja(Venda.objects.all(), user)
    no_intervalo = filtrar_por_intervalo(vendas, inicio, fim).aggregate(
        total=soma_das_vendas(), ticket=Coalesce(Avg('valor_total'), _ZERO, output_field=_DINHEIRO),
    )
    periodos = inicios_dos_periodos(agora)
    por_periodo = faturamento_por_periodo(
        vendas, {nome: periodos[nome] for nome in ('hoje', 'semana', 'mes', 'ano')},
    )

    clientes = filtrar_por_loja(Cliente.objects.com_saldo(), user)
    devendo = list(clientes.filter(saldo_calculado__gt=0).order_by('-saldo_calculado'))
    credito = list(
        clientes.filter(saldo_calculado__lt=0)
        .annotate(valor_credito=-F('saldo_calculado'))
        .order_by('saldo_calculado')
    )

    return Relatorio(
        total_geral_vendas=no_intervalo['total'],
        ticket_medio=no_intervalo['ticket'],
        vendas_hoje_valor=por_periodo['hoje'],
        vendas_semana_valor=por_periodo['semana'],
        vendas_mes_valor=por_periodo['mes'],
        vendas_ano_valor=por_periodo['ano'],
        clientes_devendo=devendo,
        total_fiado_pendente=sum((c.saldo_calculado for c in devendo), Decimal('0.00')),
        clientes_credito=credito,
        total_credito_clientes=sum((c.valor_credito for c in credito), Decimal('0.00')),
        estoque_ordenado=list(
            filtrar_por_loja(Produto.objects.filter(controla_estoque=True), user).order_by('quantidade_estoque', 'nome')
        ),
    )


def soma_das_vendas(filtro=None):
    """Soma de valor_total (zero quando não há vendas), opcionalmente filtrada."""
    return Coalesce(Sum('valor_total', filter=filtro), _ZERO, output_field=_DINHEIRO)
