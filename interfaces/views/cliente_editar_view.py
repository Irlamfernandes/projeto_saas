from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.cliente import Cliente

@login_required
def cliente_editar_view(request, pk):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=pk)
    else:
        cliente = get_object_or_404(Cliente, pk=pk, loja=request.user.loja)

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()
        endereco = request.POST.get('endereco', '').strip()

        if not nome:
            messages.error(request, "O nome do cliente é obrigatório.")
            return redirect('clientes')

        if len(nome) > 255 or len(telefone) > 20 or len(email) > 254:
            messages.error(request, "Um ou mais campos excedem o tamanho máximo permitido.")
            return redirect('clientes')

        cliente.nome = nome
        cliente.telefone = telefone if telefone else None
        cliente.email = email if email else None
        cliente.endereco = endereco if endereco else None
        
        try:
            cliente.full_clean()
            cliente.save()
            messages.success(request, "Cliente atualizado com sucesso!")
        except ValidationError as e:
            messages.error(request, "Erro de validação ao atualizar o cliente.")
        
    return redirect('clientes')