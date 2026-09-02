from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from infrastructure.models.cliente import Cliente

@login_required
def cliente_editar_view(request, pk):
    loja_usuario = request.user.loja
    
    cliente = get_object_or_404(Cliente, pk=pk, loja=loja_usuario)

    if request.method == 'POST':
        cliente.nome = request.POST.get('nome')
        cliente.telefone = request.POST.get('telefone')
        cliente.email = request.POST.get('email')
        cliente.endereco = request.POST.get('endereco')
        
        cliente.save()
        
    return redirect('clientes')