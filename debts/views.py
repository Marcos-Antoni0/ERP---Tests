from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views import View

from clients.models import Client
from core.utils import get_user_company
from debts.models import Debt


class DebtListView(LoginRequiredMixin, View):
    template_name = 'debts/list.html'

    def get(self, request):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('home-page')

        status_filter = request.GET.get('status', 'open')
        base_qs = Debt.objects.filter(company=company).select_related('client')
        if status_filter in {Debt.Status.OPEN, Debt.Status.PAID}:
            debts = base_qs.filter(status=status_filter)
        else:
            debts = base_qs

        clients = Client.objects.filter(company=company).order_by('name')
        stats = {
            'open_total': Debt.aggregate_total(company=company, status=Debt.Status.OPEN),
            'paid_total': Debt.aggregate_total(company=company, status=Debt.Status.PAID),
            'count_open': base_qs.filter(status=Debt.Status.OPEN).count(),
        }

        return render(
            request,
            self.template_name,
            {
                'debts': debts,
                'clients': clients,
                'stats': stats,
                'status_filter': status_filter,
                'current': 'debts-list',
            },
        )

    def post(self, request):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('home-page')

        client_id = request.POST.get('client_id')
        amount_raw = request.POST.get('amount', '0')
        description = (request.POST.get('description') or '').strip()
        due_date = request.POST.get('due_date') or None

        try:
            client = Client.objects.get(pk=client_id, company=company)
        except Client.DoesNotExist:
            messages.error(request, 'Cliente inválido para registrar débito.')
            return redirect(reverse('debts-list'))

        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            messages.error(request, 'Valor do débito inválido.')
            return redirect(reverse('debts-list'))

        if amount <= 0:
            messages.error(request, 'O valor do débito deve ser maior que zero.')
            return redirect(reverse('debts-list'))

        Debt.objects.create(
            company=company,
            client=client,
            amount=amount,
            description=description,
            due_date=due_date or None,
        )
        messages.success(request, 'Débito registrado.')
        return redirect(reverse('debts-list'))


class DebtPayView(LoginRequiredMixin, View):
    def post(self, request, debt_id):
        company = get_user_company(request)
        if not company:
            messages.error(request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('home-page')

        debt = get_object_or_404(Debt, pk=debt_id, company=company)
        payment_method = (request.POST.get('payment_method') or '').upper()
        if debt.status == Debt.Status.PAID:
            messages.info(request, 'Este débito já está marcado como pago.')
            return redirect(reverse('debts-list'))

        debt.mark_paid(method=payment_method)
        messages.success(request, 'Débito baixado como pago.')
        return redirect(reverse('debts-list'))
