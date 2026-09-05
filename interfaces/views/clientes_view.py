from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.cliente import Cliente

@login_required
def clientes_view(request):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        clientes = Cliente.objects.all()
    else:
        clientes = Cliente.objects.filter(loja=request.user.loja)

    busca = request.GET.get('q', '').strip()
    if busca:
        if len(busca) > 100:
            messages.error(request, "O termo de busca é muito longo.")
            return redirect('clientes')
        clientes = clientes.filter(nome__icontains=busca) | clientes.filter(telefone__icontains=busca)

    clientes = clientes.order_by('-data_criacao')

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        email = request.POST.get('email', '').strip()
        endereco = request.POST.get('endereco', '').strip()

        if not nome:
            messages.error(request, "O nome do cliente é obrigatório.")
            return redirect('clientes')

        if len(nome) > 255 or len(telefone) > 20 or len(email) > 254:
            messages.error(request, "Um ou mais campos excedem o limite máximo permitido.")
            return redirect('clientes')

        loja_destino = request.user.loja if not request.user.is_superuser else None
        
        cliente = Cliente(
            loja=request.user.loja,
            nome=nome,
            telefone=telefone if telefone else None,
            email=email if email else None,
            endereco=endereco if endereco else None
        )

        try:
            cliente.full_clean()
            cliente.save()
            messages.success(request, "Cliente cadastrado com sucesso!")
        except ValidationError:
            messages.error(request, "Erro ao validar os dados do cliente.")

        return redirect('clientes')

    context = {
        'clientes': clientes,
        'filtro_busca': busca,
    }
    return render(request, 'interfaces/clientes.html', context)