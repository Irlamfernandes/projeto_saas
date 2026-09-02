from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from infrastructure.models.cliente import Cliente
from infrastructure.utils.pdf_generator import gerar_extrato_pdf_cliente

@login_required
def extrato_pdf_view(request, cliente_id):
    loja = request.user.loja
    cliente = get_object_or_404(Cliente, pk=cliente_id, loja=loja)
    
    caminho_pdf = f"/tmp/extrato_cliente_{cliente.id}.pdf"
    gerar_extrato_pdf_cliente(cliente, caminho_pdf)
    
    return FileResponse(
        open(caminho_pdf, 'rb'), 
        content_type='application/pdf', 
        as_attachment=True, 
        filename=f"extrato_{cliente.nome.replace(' ', '_')}.pdf"
    )