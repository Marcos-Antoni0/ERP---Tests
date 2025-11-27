from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from .models_tenant import TenantMixin, TenantManager


User = get_user_model()


class Category(TenantMixin):
    name = models.TextField()
    description = models.TextField()
    status = models.IntegerField(default=1)
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    def __str__(self):
        return self.name


class Products(TenantMixin):
    code = models.CharField(max_length=100)
    category_id = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    price = models.FloatField(default=0)
    status = models.IntegerField(default=1)
    custo = models.FloatField(default=0.0)
    is_combo = models.BooleanField(default=False)
    combo_total_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        help_text='Quantidade total consumida por venda do combo.',
    )
    combo_max_flavors = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Número máximo de itens diferentes permitidos por combo.',
    )
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    def __str__(self):
        return self.code + ' - ' + self.name

    def save(self, *args, **kwargs):
        # Garante que a categoria pertença à mesma empresa
        if self.category_id and self.company_id and self.category_id.company_id != self.company_id:
            raise ValueError(
                'A categoria deve pertencer à mesma empresa do produto')
        if not self.is_combo:
            self.combo_total_quantity = None
            self.combo_max_flavors = None
        super().save(*args, **kwargs)


class ProductComboItem(TenantMixin):
    combo = models.ForeignKey(
        Products,
        related_name='combo_items',
        on_delete=models.CASCADE,
    )
    component = models.ForeignKey(
        Products,
        related_name='component_of_combos',
        on_delete=models.PROTECT,
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal('0.000'),
        help_text='Quantidade padrão consumida por combo.'
    )

    objects = TenantManager()

    class Meta:
        unique_together = (('combo', 'component', 'company'),)
        verbose_name = 'Item de Combo'
        verbose_name_plural = 'Itens de Combo'

    def clean(self):
        super().clean()
        if self.combo_id and not self.combo.is_combo:
            raise ValidationError(
                'O produto selecionado não está configurado como combo.')
        if self.combo_id and self.component_id and self.combo_id == self.component_id:
            raise ValidationError(
                'O combo não pode incluir ele mesmo como componente.')
        if (
            self.component_id
            and self.company_id
            and self.component.company_id != self.company_id
        ):
            raise ValidationError(
                'O componente precisa pertencer à mesma empresa do combo.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Sales(TenantMixin):
    customer_name = models.CharField(
        'Nome do Cliente', max_length=100, blank=True, null=True)
    client = models.ForeignKey(
        'clients.Client',
        related_name='sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=100)
    sub_total = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)
    tax_amount = models.FloatField(default=0)
    tax = models.FloatField(default=0)
    tendered_amount = models.FloatField(default=0)
    amount_change = models.FloatField(default=0)
    delivery_fee = models.FloatField('Taxa de Entrega', default=0)
    discount_total = models.FloatField('Desconto aplicado', default=0)
    discount_reason = models.CharField(
        'Motivo do desconto', max_length=255, blank=True)

    FORMA_PAGAMENTO_CHOICES = [
        ('PIX', 'Pix'),
        ('DINHEIRO', 'Dinheiro'),
        ('DEBITO', 'Débito'),
        ('CREDITO', 'Crédito'),
        ('MULTI', 'Pagamentos múltiplos'),
    ]
    ORDER_STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('em_rota', 'Em rota'),
        ('entregue', 'Entregue'),
    ]
    forma_pagamento = models.CharField(
        max_length=10,
        choices=FORMA_PAGAMENTO_CHOICES,
        default='PIX',
        verbose_name='Forma de Pagamento'
    )
    endereco_entrega = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Endereço (Entrega)',
        help_text='Informe o endereço, se necessário, para ser exibido na nota.'
    )
    type = models.CharField(
        max_length=40,
        default='venda',
        help_text='Define a origem da venda (ex.: venda, pedido, Mesa 5)'
    )
    status = models.CharField(
        max_length=10,
        choices=ORDER_STATUS_CHOICES,
        default='pendente',
        help_text='Só relevante se type="pedido"'
    )
    venda_a_prazo = models.BooleanField(
        default=False,
        help_text='Indica se a venda foi concluída com saldo a receber (débito).',
    )

    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    table = models.ForeignKey(
        'Table',
        related_name='sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    table_order = models.ForeignKey(
        'TableOrder',
        related_name='sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    objects = TenantManager()

    def __str__(self):
        return self.code


class SalePayment(TenantMixin):
    sale = models.ForeignKey(
        Sales,
        related_name='payments',
        on_delete=models.CASCADE,
    )
    method = models.CharField(
        max_length=10,
        choices=Sales.FORMA_PAGAMENTO_CHOICES,
    )
    tendered_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    applied_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    change_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='sale_payments',
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    objects = TenantManager()

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Pagamento de venda'
        verbose_name_plural = 'Pagamentos de vendas'

    def __str__(self):
        return f'{self.sale.code} - {self.method} ({self.applied_amount})'


class PedidoPayment(TenantMixin):
    pedido = models.ForeignKey(
        'Pedido',
        related_name='payments',
        on_delete=models.CASCADE,
    )
    method = models.CharField(
        max_length=10,
        choices=Sales.FORMA_PAGAMENTO_CHOICES,
    )
    tendered_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    applied_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    change_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='pedido_payments',
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    objects = TenantManager()

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Pagamento de pedido'
        verbose_name_plural = 'Pagamentos de pedidos'

    def __str__(self):
        return f'{self.pedido.code} - {self.method} ({self.applied_amount})'


class Pedido(TenantMixin):
    customer_name = models.CharField(
        'Nome do Cliente', max_length=100, blank=True, null=True)
    client = models.ForeignKey(
        'clients.Client',
        related_name='orders',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    code = models.CharField(max_length=100)
    sub_total = models.FloatField(default=0)
    tax = models.FloatField(default=0)
    tax_amount = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)
    tendered_amount = models.FloatField(default=0)
    amount_change = models.FloatField(default=0)
    forma_pagamento = models.CharField(
        max_length=10,
        choices=Sales.FORMA_PAGAMENTO_CHOICES,
        default='PIX',
        verbose_name='Forma de Pagamento'
    )
    endereco_entrega = models.CharField('Endereço (Entrega)', max_length=255,
                                        blank=True, null=True)
    taxa_entrega = models.FloatField('Taxa de Entrega', default=0)
    discount_total = models.FloatField('Desconto aplicado', default=0)
    discount_reason = models.CharField(
        'Motivo do desconto', max_length=255, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Sales.ORDER_STATUS_CHOICES,
        default='pendente',
        help_text='Só relevante para pedidos'
    )
    date_added = models.DateTimeField(default=timezone.now)
    date_updated = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    def __str__(self):
        return self.code


class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    price = models.FloatField(default=0)
    qty = models.FloatField(default=0)
    taxa_entrega = models.FloatField(default=0)
    total = models.FloatField(default=0)

    def __str__(self):
        return f'{self.product.name} x {self.qty}'

    def save(self, *args, **kwargs):
        # Garante que o produto pertença à mesma empresa do pedido
        if self.product and self.pedido and self.product.company_id != self.pedido.company_id:
            raise ValueError(
                'O produto deve pertencer à mesma empresa do pedido')
        super().save(*args, **kwargs)


class PedidoComboItem(models.Model):
    pedido_item = models.ForeignKey(
        PedidoItem,
        related_name='combo_components',
        on_delete=models.CASCADE,
    )
    component = models.ForeignKey(Products, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        verbose_name = 'Componente de Combo (Pedido)'
        verbose_name_plural = 'Componentes de Combo (Pedidos)'

    def clean(self):
        super().clean()
        if self.component_id and self.pedido_item_id:
            pedido_company = self.pedido_item.pedido.company_id
            if pedido_company and self.component.company_id != pedido_company:
                raise ValidationError(
                    'O componente deve pertencer à mesma empresa do pedido.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class salesItems(models.Model):
    sale_id = models.ForeignKey(Sales, on_delete=models.CASCADE)
    product_id = models.ForeignKey(Products, on_delete=models.CASCADE)
    price = models.FloatField(default=0)
    qty = models.FloatField(default=0)
    total = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        # Garante que o produto pertença à mesma empresa da venda
        if self.product_id and self.sale_id and self.product_id.company_id != self.sale_id.company_id:
            raise ValueError(
                'O produto deve pertencer à mesma empresa da venda')
        super().save(*args, **kwargs)


class SaleComboItem(models.Model):
    sale_item = models.ForeignKey(
        salesItems,
        related_name='combo_components',
        on_delete=models.CASCADE,
    )
    component = models.ForeignKey(Products, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        verbose_name = 'Componente de Combo (Venda)'
        verbose_name_plural = 'Componentes de Combo (Vendas)'

    def clean(self):
        super().clean()
        if self.component_id and self.sale_item_id:
            sale_company = self.sale_item.sale_id.company_id
            if sale_company and self.component.company_id != sale_company:
                raise ValidationError(
                    'O componente deve pertencer à mesma empresa da venda.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Estoque(TenantMixin):
    id = models.AutoField(primary_key=True)
    produto = models.ForeignKey(Products, on_delete=models.CASCADE)
    quantidade = models.IntegerField(default=0)
    categoria = models.ForeignKey(Category, on_delete=models.CASCADE)
    VALIDADE_CHOICES = [
        (0, 'Sem Validade'),
        (30, 'Validade de 30 dias'),
        (60, 'Validade de 60 dias'),
        (90, 'Validade de 90 dias'),
        (120, 'Validade de 120 dias'),
        (180, 'Validade de 180 dias'),
        (365, 'Validade de 365 dias'),
    ]
    validade = models.IntegerField(choices=VALIDADE_CHOICES, default=0)
    descricao = models.ForeignKey(
        Products, on_delete=models.CASCADE, related_name='estoque_descricao', null=True, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    preco = models.FloatField(default=0)
    custo = models.FloatField(default=0)
    status = models.IntegerField(default=1)  # 1: Ativo, 0: Inativo

    objects = TenantManager()

    def save(self, *args, **kwargs):
        # Garante que produto e categoria pertençam à mesma empresa
        if self.produto and self.company_id and self.produto.company_id != self.company_id:
            raise ValueError(
                'O produto deve pertencer à mesma empresa do estoque')
        if self.categoria and self.company_id and self.categoria.company_id != self.company_id:
            raise ValueError(
                'A categoria deve pertencer à mesma empresa do estoque')
        super().save(*args, **kwargs)


class Garcom(TenantMixin):
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        ordering = ['name']
        unique_together = (('company', 'code'),)

    def __str__(self):
        return f'{self.code} - {self.name}' if self.code else self.name


class Table(TenantMixin):
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=120, blank=True)
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    waiter = models.ForeignKey(
        Garcom,
        related_name='current_tables',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        unique_together = ('company', 'number')
        ordering = ['number']

    def __str__(self):
        label = f'Mesa {self.number}'
        if self.name:
            label = f'{label} - {self.name}'
        return label

    def clean(self):
        super().clean()
        if self.waiter_id:
            waiter_company_id = (
                Garcom.objects.filter(pk=self.waiter_id)
                .values_list('company_id', flat=True)
                .first()
            )
            if (
                waiter_company_id is not None
                and self.company_id is not None
                and waiter_company_id != self.company_id
            ):
                raise ValidationError(
                    'O garçom deve pertencer à mesma empresa da mesa')

    @property
    def active_order(self):
        return self.orders.filter(status=TableOrder.Status.OPEN).order_by('-opened_at').first()

    @property
    def is_occupied(self):
        return self.active_order is not None


class TableOrder(TenantMixin):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberta'
        CLOSED = 'closed', 'Fechada'
        CANCELED = 'canceled', 'Cancelada'

    table = models.ForeignKey(
        Table, related_name='orders', on_delete=models.PROTECT)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN)
    waiter = models.ForeignKey(
        Garcom,
        related_name='orders',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    waiter_name = models.CharField(max_length=150, blank=True)
    people_count = models.PositiveIntegerField(default=1)
    service_charge = models.DecimalField(
        max_digits=8, decimal_places=2, default=0)
    discount_amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=0)
    discount_reason = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(
        max_length=10, choices=Sales.FORMA_PAGAMENTO_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f'Comanda {self.id} - Mesa {self.table.number}'

    def clean(self):
        table_company_id = None
        if self.table_id:
            table_company_id = Table.objects.filter(
                pk=self.table_id).values_list('company_id', flat=True).first()

        if (
            table_company_id is not None
            and self.company_id is not None
            and table_company_id != self.company_id
        ):
            raise ValidationError(
                'A mesa deve pertencer à mesma empresa da comanda')

        if self.waiter_id:
            waiter_company_id = (
                Garcom.objects.filter(pk=self.waiter_id)
                .values_list('company_id', flat=True)
                .first()
            )
            if (
                waiter_company_id is not None
                and self.company_id is not None
                and waiter_company_id != self.company_id
            ):
                raise ValidationError(
                    'O garçom deve pertencer à mesma empresa da comanda')

        discount_value = Decimal(self.discount_amount or 0)
        reason = (self.discount_reason or '').strip()
        if discount_value <= Decimal('0'):
            self.discount_reason = ''
        else:
            self.discount_reason = reason[:255]

    def _quantize_currency(self, value):
        return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def get_service_amount(self, subtotal=None):
        base = Decimal(self.subtotal if subtotal is None else subtotal or 0)
        rate = Decimal(self.service_charge or 0)
        if not rate:
            return Decimal('0.00')
        return (base * rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def recalculate_totals(self, commit=True):
        subtotal = self.items.aggregate(total=Sum('total'))[
            'total'] or Decimal('0.00')
        subtotal = self._quantize_currency(subtotal)
        discount = self._quantize_currency(self.discount_amount or 0)
        service_amount = self.get_service_amount(subtotal=subtotal)
        total = subtotal + service_amount - discount
        if total < Decimal('0.00'):
            total = Decimal('0.00')
        total = self._quantize_currency(total)
        self.subtotal = subtotal
        self.total = total
        self._service_amount_cache = service_amount
        if commit:
            self.save(update_fields=['subtotal', 'total'])
        return self.total

    @property
    def service_amount(self):
        if hasattr(self, '_service_amount_cache'):
            return self._service_amount_cache
        return self.get_service_amount()

    def save(self, *args, **kwargs):
        if self.waiter:
            self.waiter_name = self.waiter.name
        else:
            self.waiter_name = ''
        discount_value = Decimal(self.discount_amount or 0)
        if discount_value <= Decimal('0'):
            self.discount_reason = ''
        else:
            self.discount_reason = (self.discount_reason or '').strip()[:255]
        super().save(*args, **kwargs)


class TableOrderItem(models.Model):
    order = models.ForeignKey(
        TableOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Products, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    notes = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['added_at']

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'

    def clean(self):
        if self.product_id and self.order_id:
            product_company_id = (
                Products.objects.filter(pk=self.product_id)
                .values_list('company_id', flat=True)
                .first()
            )
            order_company_id = (
                TableOrder.objects.filter(pk=self.order_id)
                .values_list('company_id', flat=True)
                .first()
            )
            if (
                product_company_id is not None
                and order_company_id is not None
                and product_company_id != order_company_id
            ):
                raise ValidationError(
                    'O produto deve pertencer à mesma empresa da comanda')

    def save(self, *args, **kwargs):
        self.unit_price = Decimal(self.unit_price)
        self.quantity = Decimal(self.quantity)
        self.total = (self.unit_price *
                      self.quantity).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
        self.order.recalculate_totals(commit=True)

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.recalculate_totals(commit=True)


class CashRegisterSession(TenantMixin):
    class Status(models.TextChoices):
        OPEN = 'open', 'Aberto'
        CLOSED = 'closed', 'Fechado'

    opened_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cash_sessions_opened',
    )
    closed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cash_sessions_closed',
        null=True,
        blank=True,
    )
    opening_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    closing_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    opening_note = models.TextField(blank=True)
    closing_note = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()

    class Meta:
        ordering = ['-opened_at']
        verbose_name = 'Sessão de caixa'
        verbose_name_plural = 'Sessões de caixa'

    def __str__(self):
        return f'Caixa {self.opened_at:%d/%m/%Y %H:%M}'

    def total_entries(self):
        return self.movements.filter(type=CashMovement.Type.ENTRY).aggregate(total=Sum('amount')).get('total') or Decimal('0.00')

    def total_exits(self):
        return self.movements.filter(type=CashMovement.Type.EXIT).aggregate(total=Sum('amount')).get('total') or Decimal('0.00')

    def expected_balance(self):
        return (Decimal(self.opening_amount) + self.total_entries() - self.total_exits()).quantize(Decimal('0.01'))


class CashMovement(TenantMixin):
    class Type(models.TextChoices):
        ENTRY = 'entry', 'Entrada'
        EXIT = 'exit', 'Saída'

    MOVEMENT_PAYMENT_CHOICES = Sales.FORMA_PAGAMENTO_CHOICES + \
        [('AJUSTE', 'Ajuste manual')]

    session = models.ForeignKey(
        CashRegisterSession,
        related_name='movements',
        on_delete=models.CASCADE,
    )
    type = models.CharField(
        max_length=5, choices=Type.choices, db_column='movement_type')
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    payment_method = models.CharField(
        max_length=10,
        choices=MOVEMENT_PAYMENT_CHOICES,
        blank=True,
    )
    description = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    sale = models.ForeignKey(
        'Sales',
        related_name='cash_movements',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='cash_movements',
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    objects = TenantManager()

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Movimentação de caixa'
        verbose_name_plural = 'Movimentações de caixa'

    def __str__(self):
        return f'{self.get_type_display()} - {self.amount}'

    @property
    def signed_amount(self):
        value = Decimal(self.amount)
        return value if self.type == self.Type.ENTRY else -value
