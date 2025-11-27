from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.utils import timezone
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from core.forms import ConfiguracaoSistemaForm
from core.utils import get_user_company
from p_v_App.models import Category, Products, Sales
from debts.models import Debt


@login_required
def home(request):
    user_company = get_user_company(request)
    today = timezone.localdate()

    if user_company:
        categories = Category.objects.filter(company=user_company).count()
        products = Products.objects.filter(company=user_company).count()
        today_sales = Sales.objects.filter(
            date_added__date=today, company=user_company)
        debts_qs = Debt.objects.filter(company=user_company, status=Debt.Status.OPEN)
        debt_total_pending = Debt.aggregate_total(
            company=user_company, status=Debt.Status.OPEN)
        debt_clients_with_pending = (
            debts_qs.exclude(client__isnull=True)
            .values('client_id')
            .distinct()
            .count()
        )
        debt_overdue = debts_qs.filter(due_date__lt=today).count()
    else:
        categories = 0
        products = 0
        today_sales = Sales.objects.none()
        debt_total_pending = 0
        debt_clients_with_pending = 0
        debt_overdue = 0

    context = {
        'page_title': 'Início',
        'categories': categories,
        'products': products,
        'transaction': today_sales.count(),
        'total_sales': today_sales.aggregate(total=Sum('grand_total'))['total'] or 0,
        'debt_total_pending': debt_total_pending,
        'debt_clients_with_pending': debt_clients_with_pending,
        'debt_overdue': debt_overdue,
    }
    return render(request, 'core/home.html', context)


@login_required
def about(request):
    return redirect(reverse_lazy('configuracoes-page'))


class ConfiguracoesView(LoginRequiredMixin, TemplateView):
    template_name = 'core/configuracoes.html'
    form_class = ConfiguracaoSistemaForm

    def get_company(self):
        return get_user_company(self.request)

    def get_printer_choices(self):
        try:
            import win32print

            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            names = []
            for printer in printers:
                # EnumPrinters returns tuples where the last element is the printer name
                name = printer[-1]
                if name:
                    names.append(str(name))
            return sorted(set(names))
        except Exception:
            # Em ambientes sem suporte (Linux/containers), não falhar; manter entrada manual
            return []

    def get_form(self):
        return self.form_class(
            instance=self.get_company(),
            printer_choices=self.get_printer_choices(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        printers = self.get_printer_choices()
        context.update(
            {
                'page_title': 'Configurações',
                'form': kwargs.get('form') or self.get_form(),
                'printers': printers,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        company = self.get_company()
        if not company:
            messages.error(
                request,
                'Não foi possível identificar sua empresa. Verifique seu perfil ou contate o administrador.',
            )
            return redirect('home-page')

        form = self.form_class(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Configurações atualizadas para o tenant atual.',
            )
            return redirect('configuracoes-page')

        return self.render_to_response(self.get_context_data(form=form))
