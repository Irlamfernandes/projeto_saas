import io
import re
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from application.clientes.selectors import clientes_do_usuario
from infrastructure.utils.pdf_generator import gerar_extrato_pdf_cliente
from interfaces.decorators import loja_required


@loja_required
def extrato_pdf_view(request, cliente_id):
    clientes = clientes_do_usuario(request.user).com_saldo().select_related('loja')
    cliente = get_object_or_404(clientes, pk=cliente_id)

    pdf_buffer = io.BytesIO()
    gerar_extrato_pdf_cliente(cliente, pdf_buffer)
    pdf_buffer.seek(0)

    nome_sanitizado = re.sub(r'[^a-zA-Z0-9_-]', '_', cliente.nome)
    return FileResponse(
        pdf_buffer,
        content_type='application/pdf',
        as_attachment=True,
        filename=f"extrato_{nome_sanitizado}.pdf",
    )
