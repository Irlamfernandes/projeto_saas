import io
import re
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from interfaces.decorators import loja_required
from infrastructure.models.cliente import Cliente
from infrastructure.utils.pdf_generator import gerar_extrato_pdf_cliente

@loja_required
def extrato_pdf_view(request, cliente_id):
    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
    else:
        cliente = get_object_or_404(Cliente, pk=cliente_id, loja=request.user.loja)

    pdf_buffer = io.BytesIO()
    gerar_extrato_pdf_cliente(cliente, pdf_buffer)
    pdf_buffer.seek(0)

    nome_sanitizado = re.sub(r'[^a-zA-Z0-9_-]', '_', cliente.nome)
    filename = f"extrato_{nome_sanitizado}.pdf"

    response = FileResponse(
        pdf_buffer, 
        content_type='application/pdf', 
        as_attachment=True, 
        filename=filename
    )
    return response