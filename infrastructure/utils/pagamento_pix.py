import requests
from django.conf import settings

def criar_cobranca_pix_mercadopago(fatura):
    """
    Cria um pagamento via Pix no Mercado Pago para a fatura informada.
    Retorna um dicionário com o ID da transação, o código Copia e Cola e a URL do QR Code.
    """
    access_token = getattr(settings, 'MERCADO_PAGO_ACCESS_TOKEN', 'TEST-TOKEN-MOCK')
    
    url = "https://api.mercadopago.com/v1/payments"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(fatura.id)
    }
    
    titulos_planos = {
        '1_MES': 'Assinatura Mensal - SaaS',
        '3_MESES': 'Assinatura Trimestral - SaaS',
        '6_MESES': 'Assinatura Semestral - SaaS',
        '1_ANO': 'Assinatura Anual - SaaS',
    }
    
    payload = {
        "transaction_amount": float(fatura.valor),
        "description": titulos_planos.get(fatura.plano, 'Assinatura SaaS'),
        "payment_method_id": "pix",
        "payer": {
            "email": f"financeiro@{fatura.loja.pk}.com",
            "first_name": fatura.loja.nome_loja,
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if response.status_code in [200, 201]:
            data = response.json()
            point_of_interaction = data.get("point_of_interaction", {})
            transaction_data = point_of_interaction.get("transaction_data", {})
            
            return {
                "sucesso": True,
                "id_transacao": str(data.get("id")),
                "qr_code_pix": transaction_data.get("qr_code"),
                "qr_code_imagem_url": transaction_data.get("qr_code_base64")
            }
        else:
            return {
                "sucesso": False,
                "erro": response.json().get("message", "Erro desconhecido na API do Mercado Pago")
            }
            
    except requests.exceptions.RequestException as e:
        return {
            "sucesso": False,
            "erro": str(e)
        }