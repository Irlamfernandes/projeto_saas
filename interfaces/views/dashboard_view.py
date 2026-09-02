from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from infrastructure.models import Produto

@login_required
def dashboard_view(request):
    total_produtos = Produto.objects.filter(loja=request.user.loja).count()

    context = {
        'total_produtos': total_produtos,
    }
    return render(request, 'interfaces/dashboard.html', context)