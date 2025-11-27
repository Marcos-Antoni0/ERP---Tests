from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from p_v_App.models_tenant import TenantMixin, TenantManager
from p_v_App.models import Sales


class Debt(TenantMixin):
    class Status(models.TextChoices):
        OPEN = 'open', 'Em aberto'
        PAID = 'paid', 'Pago'

    client = models.ForeignKey(
        'clients.Client',
        related_name='debts',
        on_delete=models.CASCADE,
    )
    sale = models.ForeignKey(
        Sales,
        related_name='linked_debts',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Venda de origem para rastreabilidade do débito.',
    )
    description = models.CharField('Descrição', max_length=255, blank=True)
    amount = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
    )
    due_date = models.DateField('Vencimento', null=True, blank=True)
    payment_method = models.CharField(
        'Forma de pagamento',
        max_length=20,
        blank=True,
    )
    paid_at = models.DateTimeField('Pago em', null=True, blank=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = 'Débito'
        verbose_name_plural = 'Débitos'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.client.name} - R$ {self.amount}'

    def mark_paid(self, method: str | None = None):
        self.status = self.Status.PAID
        self.payment_method = method or self.payment_method or ''
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'payment_method', 'paid_at'])

    @classmethod
    def aggregate_total(cls, **filters):
        total = (
            cls.objects.filter(**filters)
            .aggregate(total=Sum('amount'))
            .get('total')
            or Decimal('0')
        )
        return Decimal(str(total))
