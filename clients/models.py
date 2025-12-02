from decimal import Decimal

from django.db import models
from django.db.models import Sum

from p_v_App.models_tenant import TenantMixin, TenantManager


class Client(TenantMixin):
    name = models.CharField('Nome', max_length=150)
    cpf = models.CharField('CPF', max_length=14, blank=True, null=True, unique=True)
    phone = models.CharField('Telefone', max_length=30, blank=True)
    address = models.TextField('Endereço', blank=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    @property
    def total_consumption(self) -> Decimal:
        from p_v_App.models import Sales  # local import to avoid cycles

        total = (
            Sales.objects.filter(company=self.company, client=self)
            .aggregate(total=Sum('grand_total'))
            .get('total')
            or 0
        )
        return Decimal(str(total))

    @property
    def pending_debt_total(self) -> Decimal:
        from debts.models import Debt  # local import to avoid cycles

        total = (
            Debt.objects.filter(company=self.company, client=self, status=Debt.Status.OPEN)
            .aggregate(total=Sum('amount'))
            .get('total')
            or 0
        )
        return Decimal(str(total))
