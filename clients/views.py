from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from core.utils import get_user_company
from clients.models import Client
from debts.models import Debt


class ClientListView(LoginRequiredMixin, View):
    template_name = 'clients/list.html'

    def get(self, request):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('home-page')

        clients = Client.objects.filter(company=company).order_by('name')
        stats = {
            'total_clients': clients.count(),
            'pending_total': Debt.aggregate_total(company=company, status=Debt.Status.OPEN),
            'consumption_total': self._sum_consumption(clients),
        }
        return render(
            request,
            self.template_name,
            {
                'clients': clients,
                'stats': stats,
                'current': 'clients-list',
            },
        )

    def post(self, request):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('home-page')

        name = (request.POST.get('name') or '').strip()
        email = (request.POST.get('email') or '').strip() or None
        phone = (request.POST.get('phone') or '').strip()
        address = (request.POST.get('address') or '').strip()

        if not name:
            messages.error(request, 'Informe o nome do cliente.')
            return redirect(reverse('clients-list'))

        Client.objects.create(
            company=company,
            name=name,
            email=email,
            phone=phone,
            address=address,
        )
        messages.success(request, 'Cliente cadastrado com sucesso.')
        return redirect(reverse('clients-list'))

    def _sum_consumption(self, clients):
        total = Decimal('0')
        for client in clients:
            total += client.total_consumption or Decimal('0')
        return total
