from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from infrastructure.models.cliente import Cliente

@login_required
def clientes_view(request):
    loja_usuario = request.user.loja

    clientes = Cliente.objects.filter(loja=loja_usuario)

    busca = request.GET.get('q', '').strip()
    if busca:
        clientes = clientes.filter(nome__icontains=busca) | clientes.filter(telefone__icontains=busca)

    clientes = clientes.order_by('-data_criacao')

    if request.method == 'POST':
        nome = request.POST.get('nome')
        telefone = request.POST.get('telefone')
        email = request.POST.get('email')
        endereco = request.POST.get('endereco')

        Cliente.objects.create(
            loja=loja_usuario,
            nome=nome,
            telefone=telefone,
            email=email,
            endereco=endereco
        )
        return redirect('clientes')

    context = {
        'clientes': clientes,
        'filtro_busca': busca,
    }
    return render(request, 'interfaces/clientes.html', context)