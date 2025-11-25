from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.db.models import Sum
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

        search_term = (request.GET.get('q') or '').strip()
        base_qs = Client.objects.filter(company=company)
        if search_term:
            base_qs = base_qs.filter(name__icontains=search_term)

        clients = base_qs.order_by('name')
        stats = {
            'total_clients': Client.objects.filter(company=company).count(),
            'pending_total': Debt.aggregate_total(company=company, status=Debt.Status.OPEN),
            'consumption_total': self._sum_consumption(company),
        }
        return render(
            request,
            self.template_name,
            {
                'clients': clients,
                'stats': stats,
                'current': 'clients-list',
                'search_term': search_term,
            },
        )

    def post(self, request):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('home-page')

        client_id = request.POST.get('client_id')
        action = (request.POST.get('action') or '').lower()

        if action == 'delete':
            if not client_id:
                messages.error(request, 'Cliente inválido para exclusão.')
                return redirect(reverse('clients-list'))
            try:
                client = Client.objects.get(pk=client_id, company=company)
            except Client.DoesNotExist:
                messages.error(request, 'Cliente não encontrado para exclusão.')
            else:
                client.delete()
                messages.success(request, f'Cliente {client.name} excluído com sucesso.')
            return redirect(reverse('clients-list'))

        name = (request.POST.get('name') or '').strip()
        cpf_raw = (request.POST.get('cpf') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        address = (request.POST.get('address') or '').strip()

        if not name:
            messages.error(request, 'Informe o nome do cliente.')
            return redirect(reverse('clients-list'))

        cpf_digits = ''.join(ch for ch in cpf_raw if ch.isdigit())
        if cpf_digits and len(cpf_digits) != 11:
            messages.error(request, 'Informe um CPF válido com 11 dígitos ou deixe em branco.')
            return redirect(reverse('clients-list'))

        payload = {
            'name': name,
            'cpf': cpf_digits or None,
            'phone': phone,
            'address': address,
        }

        try:
            if client_id:
                try:
                    client = Client.objects.get(pk=client_id, company=company)
                except Client.DoesNotExist:
                    messages.error(request, 'Cliente não encontrado para edição.')
                    return redirect(reverse('clients-list'))

                for field, value in payload.items():
                    setattr(client, field, value)
                client.save(update_fields=list(payload.keys()))
                messages.success(request, 'Cliente atualizado com sucesso.')
            else:
                Client.objects.create(company=company, **payload)
                messages.success(request, 'Cliente cadastrado com sucesso.')
        except IntegrityError:
            messages.error(request, 'Já existe um cliente com este CPF.')

        return redirect(reverse('clients-list'))

    def _sum_consumption(self, company):
        from p_v_App.models import Sales  # local import to avoid cycles

        total = (
            Sales.objects.filter(company=company, client__company=company)
            .aggregate(total=Sum('grand_total'))
            .get('total')
            or 0
        )
        return Decimal(str(total))
