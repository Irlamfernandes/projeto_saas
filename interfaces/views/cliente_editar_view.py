from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.cliente import Cliente


def _obter_cliente_autorizado(request, pk):
    """Auxiliar para verificar permissões e buscar o cliente com segurança."""
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        return get_object_or_404(Cliente, pk=pk)
    
    return get_object_or_404(Cliente, pk=pk, loja=request.user.loja)


@login_required
def cliente_editar_view(request, pk):
    cliente = _obter_cliente_autorizado(request, pk)

    if request.method != 'POST':
        return redirect('clientes')

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
    cliente.telefone = telefone or None
    cliente.email = email or None
    cliente.endereco = endereco or None
    
    try:
        cliente.full_clean()
        cliente.save()
        messages.success(request, "Cliente atualizado com sucesso!")
    except ValidationError:
        messages.error(request, "Erro de validação ao atualizar o cliente.")
    
    return redirect('clientes')