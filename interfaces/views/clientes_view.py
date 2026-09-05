from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.cliente import Cliente

TEMPLATE_CLIENTES = 'interfaces/clientes.html'


def _obter_clientes_autorizados(user):
    """Retorna o queryset base de clientes de acordo com as permissões do usuário."""
    if not user.is_superuser and not user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")
    
    if user.is_superuser:
        return Cliente.objects.all()
    return Cliente.objects.filter(loja=user.loja)


def _processar_busca(request, clientes):
    """Filtra o queryset de clientes com base no termo de busca fornecido."""
    busca = request.GET.get('q', '').strip()
    if not busca:
        return clientes, ''

    if len(busca) > 100:
        messages.error(request, "O termo de busca é muito longo.")
        return None, busca

    clientesfiltrados = clientes.filter(nome__icontains=busca) | clientes.filter(telefone__icontains=busca)
    return clientesfiltrados, busca


def _processar_cadastro_cliente(request):
    """Processa a requisição POST para cadastrar um novo cliente."""
    nome = request.POST.get('nome', '').strip()
    telefone = request.POST.get('telefone', '').strip()
    email = request.POST.get('email', '').strip()
    endereco = request.POST.get('endereco', '').strip()

    if not nome:
        messages.error(request, "O nome do cliente é obrigatório.")
        return

    if len(nome) > 255 or len(telefone) > 20 or len(email) > 254:
        messages.error(request, "Um ou mais campos excedem o tamanho máximo permitido.")
        return

    cliente = Cliente(
        loja=request.user.loja,
        nome=nome,
        telefone=telefone or None,
        email=email or None,
        endereco=endereco or None
    )

    try:
        cliente.full_clean()
        cliente.save()
        messages.success(request, "Cliente cadastrado com sucesso!")
    except ValidationError:
        messages.error(request, "Erro ao validar os dados do cliente.")


@login_required
def clientes_view(request):
    clientes = _obter_clientes_autorizados(request.user)

    if request.method == 'POST':
        _processar_cadastro_cliente(request)
        return redirect('clientes')

    clientes, busca = _processar_busca(request, clientes)
    if clientes is None:
        return redirect('clientes')

    clientes = clientes.order_by('-data_criacao')

    context = {
        'clientes': clientes,
        'filtro_busca': busca,
    }
    return render(request, TEMPLATE_CLIENTES, context)