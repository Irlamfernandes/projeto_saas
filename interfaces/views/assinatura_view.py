from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.fatura_assinatura import FaturaAssinatura
from infrastructure.utils.pagamento_pix import criar_cobranca_pix_mercadopago

TEMPLATE_SELECIONAR_PLANO = 'interfaces/selecionar_plano.html'
TEMPLATE_PAGAR_PIX = 'interfaces/pagar_pix.html'


def _verificar_permissao_loja(user, loja):
    """Garante que o usuário tem acesso à loja solicitada."""
    if not user.is_superuser and user.loja != loja:
        raise PermissionDenied("Acesso negado: Você não tem permissão para gerenciar esta loja.")


def _obter_planos_disponiveis():
    """Retorna a listagem de planos e valores do SaaS."""
    return [
        {'id': '1_MES', 'nome': 'Mensal', 'valor': '70.00', 'detalhe': 'R$ 70,00 por mês'},
        {'id': '3_MESES', 'nome': 'Trimestral', 'valor': '210.00', 'detalhe': 'Equivalente a R$ 70,00/mês'},
        {'id': '6_MESES', 'nome': 'Semestral', 'valor': '360.00', 'detalhe': 'Equivalente a R$ 60,00/mês'},
        {'id': '1_ANO', 'nome': 'Anual', 'valor': '660.00', 'detalhe': 'R$ 55,00 por mês (Melhor valor)'},
    ]


def _processar_criacao_fatura(request, loja):
    """Processa a escolha do plano e gera a fatura e o Pix via Mercado Pago."""
    plano = request.POST.get('plano', '').strip()
    
    valores_planos = {
        '1_MES': Decimal('70.00'),
        '3_MESES': Decimal('210.00'),
        '6_MESES': Decimal('360.00'),
        '1_ANO': Decimal('660.00'),
    }
    
    valor = valores_planos.get(plano)
    
    if not valor:
        messages.error(request, "Selecione um plano válido para continuar.")
        return None

    fatura = FaturaAssinatura(
        loja=loja,
        plano=plano,
        valor=valor,
        status='PENDENTE'
    )

    try:
        fatura.full_clean()
        fatura.save()
    except ValidationError:
        messages.error(request, "Erro ao validar os dados da fatura.")
        return None

    # Integração com Mercado Pago
    resultado = criar_cobranca_pix_mercadopago(fatura)

    if resultado['sucesso']:
        fatura.id_transacao_gateway = resultado['id_transacao']
        fatura.qr_code_pix = resultado['qr_code_pix']
        fatura.qr_code_imagem_url = resultado['qr_code_imagem_url']
        fatura.save()
        return fatura
    else:
        fatura.status = 'CANCELADO'
        fatura.save()
        erro_msg = resultado.get('erro', 'Erro desconhecido ao gerar cobrança Pix.')
        messages.error(request, f"Falha no gateway de pagamento: {erro_msg}")
        return None


@login_required
def assinatura_view(request, loja_id):
    """Exibe os planos e gerencia a solicitação de pagamento Pix da loja."""
    loja = get_object_or_404(LojaModel, id=loja_id)
    _verificar_permissao_loja(request.user, loja)

    if request.method == 'POST':
        fatura = _processar_criacao_fatura(request, loja)
        if fatura:
            context = {
                'loja': loja,
                'fatura': fatura,
            }
            return render(request, TEMPLATE_PAGAR_PIX, context)
        return redirect('assinatura', loja_id=loja.id)

    context = {
        'loja': loja,
        'planos': _obter_planos_disponiveis(),
    }
    return render(request, TEMPLATE_SELECIONAR_PLANO, context)