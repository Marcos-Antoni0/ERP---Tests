from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, transaction
from django.db.models import Q, Sum, Max
from django.db.models.functions import TruncDate
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.utils import timezone

from p_v_App.models import Garcom, Estoque, Sales, Table, TableOrder, TableOrderItem, salesItems
from p_v_App.models_tenant import Company
from sales.utils import register_sale_payments


def get_user_company(request) -> Optional[Company]:
    """Return the company associated with the authenticated user."""
    if hasattr(request.user, 'profile') and request.user.profile.company:
        return request.user.profile.company
    if request.user.is_superuser:
        return Company.objects.first()
    return None


def table_models_ready() -> bool:
    """Check if the database contains all tables required for table management."""
    try:
        existing_tables = set(connection.introspection.table_names())
    except (ProgrammingError, OperationalError):
        return False

    required = {
        Garcom._meta.db_table,
        Table._meta.db_table,
        TableOrder._meta.db_table,
        TableOrderItem._meta.db_table,
    }
    return required.issubset(existing_tables)


def guard_tables_ready(request, redirect_name: str = 'mesas'):
    """Ensure table related database objects exist before continuing."""
    if table_models_ready():
        return True

    messages.error(
        request,
        (
            'As estruturas de mesas e comandas ainda não foram aplicadas ao banco. '
            'Execute "python manage.py migrate" e tente novamente.'
        ),
    )
    return redirect(redirect_name)


def generate_sale_code(company: Company, extra_querysets=None) -> str:
    if extra_querysets is None:
        extra_querysets = []
    prefix = timezone.now().year * 2
    prefix_str = str(prefix)

    def _max_sequence(qs) -> int:
        """Extract the highest numeric suffix for codes that start with the prefix."""
        max_code = (
            qs.filter(code__startswith=prefix_str)
            .aggregate(max_code=Max('code'))
            .get('max_code')
        )
        if not max_code:
            return 0
        suffix = str(max_code)[len(prefix_str):]
        return int(suffix) if suffix.isdigit() else 0

    max_idx = _max_sequence(Sales.objects.filter(company=company))
    for qs in extra_querysets:
        max_idx = max(max_idx, _max_sequence(qs))

    next_idx = max_idx + 1
    while True:
        code = f'{prefix}{next_idx:05d}'
        if not Sales.objects.filter(company=company, code=code).exists() and all(
            not qs.filter(code=code).exists() for qs in extra_querysets
        ):
            return code
        next_idx += 1


def _to_decimal(value, default: str = '0') -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (TypeError, InvalidOperation):
        return Decimal(default)


def serialize_receipt_items(items: Iterable) -> list[dict]:
    """Normalize items from sales/orders for display in receipts."""
    normalized = []
    for index, item in enumerate(items, start=1):
        quantity = _to_decimal(
            getattr(item, 'qty', getattr(item, 'quantity', 0)))
        unit_price = _to_decimal(
            getattr(item, 'price', getattr(item, 'unit_price', 0)))
        line_total = _to_decimal(getattr(item, 'total', 0))

        product_obj = None
        if hasattr(item, 'product'):
            try:
                product_obj = getattr(item, 'product')
            except ObjectDoesNotExist:
                product_obj = None
        if not product_obj and hasattr(item, 'product_id'):
            try:
                product_obj = getattr(item, 'product_id')
            except ObjectDoesNotExist:
                product_obj = None

        if product_obj is not None:
            product_name = getattr(product_obj, 'name', str(product_obj))
        else:
            product_name = f'Item #{index}'

        combo_details = []
        combo_manager = getattr(item, 'combo_components', None)
        if combo_manager is not None:
            try:
                components = list(combo_manager.all())
            except TypeError:
                components = []
            for component in components:
                try:
                    comp_name = component.component.name
                except ObjectDoesNotExist:
                    comp_name = str(component.component_id)
                combo_details.append(
                    f'{_to_decimal(component.quantity)}x {comp_name}')
        if combo_details:
            product_name = f"{product_name} ({', '.join(combo_details)})"

        normalized.append(
            {
                'quantity': quantity,
                'unit_price': unit_price,
                'total': line_total,
                'name': product_name,
            }
        )

    return normalized


def create_sale_from_table_order(
    order: TableOrder,
    company: Company,
    *,
    allocations: Sequence[dict],
    tendered_total: Decimal,
    change_total: Decimal,
    primary_method: str,
    user,
) -> Sales:
    table = order.table
    sale_code = generate_sale_code(company)

    sale = Sales.objects.create(
        company=company,
        code=sale_code,
        customer_name=f'Mesa {table.number}',
        sub_total=float(order.subtotal),
        tax=0,
        tax_amount=0,
        grand_total=float(order.total),
        tendered_amount=float(tendered_total),
        amount_change=float(change_total),
        forma_pagamento=primary_method or 'PIX',
        type=f'Mesa {table.number}',
        status='entregue',
        delivery_fee=0,
        discount_total=float(order.discount_amount or 0),
        discount_reason=(order.discount_reason if (
            order.discount_amount or 0) > 0 else ''),
        table=table,
        table_order=order,
    )

    register_sale_payments(sale, allocations, user)

    items = order.items.select_related('product').all()
    for item in items:
        salesItems.objects.create(
            sale_id=sale,
            product_id=item.product,
            price=float(item.unit_price),
            qty=float(item.quantity),
            total=float(item.total),
        )
        try:
            estoque_item = Estoque.objects.get(
                produto=item.product, company=company)
            estoque_item.quantidade -= float(item.quantity)
            estoque_item.save(update_fields=['quantidade'])
        except Estoque.DoesNotExist:
            pass

    return sale


def reopen_table_order(order: TableOrder, company: Company):
    if order.status == TableOrder.Status.OPEN:
        return 'info', 'A comanda já está aberta.'

    if order.table.orders.filter(status=TableOrder.Status.OPEN).exclude(pk=order.pk).exists():
        return 'error', 'Já existe outra comanda aberta para esta mesa.'

    with transaction.atomic():
        sale = order.sales.filter(
            company=company).order_by('-date_added').first()
        if sale:
            sale_items = list(
                salesItems.objects.filter(sale_id=sale)
                .select_related('product_id')
                .prefetch_related('combo_components__component')
            )
            for sale_item in sale_items:
                if getattr(sale_item.product_id, 'is_combo', False):
                    for combo in sale_item.combo_components.all():
                        try:
                            estoque_item = Estoque.objects.get(
                                produto=combo.component,
                                company=company,
                            )
                            estoque_item.quantidade += float(combo.quantity)
                            estoque_item.save(update_fields=['quantidade'])
                        except Estoque.DoesNotExist:
                            pass
                else:
                    try:
                        estoque_item = Estoque.objects.get(
                            produto=sale_item.product_id,
                            company=company,
                        )
                        estoque_item.quantidade += float(sale_item.qty)
                        estoque_item.save(update_fields=['quantidade'])
                    except Estoque.DoesNotExist:
                        pass
            salesItems.objects.filter(sale_id=sale).delete()
            sale.delete()

        order.status = TableOrder.Status.OPEN
        order.closed_at = None
        order.payment_method = ''
        order.save(update_fields=['status', 'closed_at', 'payment_method'])
        order.recalculate_totals()

        table = order.table
        table.waiter = order.waiter
        table.save(update_fields=['waiter'])

    return 'success', 'Comanda reaberta.'


def get_date_range_from_request(request, delta_days: int = 30) -> tuple[datetime, datetime]:
    """Parse start/end dates from request querystring.

    Accepts both `start_date`/`end_date` and legacy `start`/`end` keys.
    Falls back to the last `delta_days` ending today when not provided/invalid.
    """
    today = timezone.now().date()

    # Prefer descriptive keys used by templates; fallback to legacy ones.
    end_date_str = (request.GET.get('end_date')
                    or request.GET.get('end') or '').strip()
    start_date_str = (request.GET.get('start_date')
                      or request.GET.get('start') or '').strip()

    try:
        end_date = datetime.strptime(
            end_date_str, '%Y-%m-%d').date() if end_date_str else today
    except ValueError:
        end_date = today

    try:
        start_date = (
            datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if start_date_str
            else today - timedelta(days=delta_days)
        )
    except ValueError:
        start_date = today - timedelta(days=delta_days)

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date


def get_report_queryset(start, end, user_company=None):
    qs = salesItems.objects.filter(
        (Q(sale_id__type__in=['venda', 'pedido'])
         | Q(sale_id__type__istartswith='Mesa')),
        sale_id__date_added__date__gte=start,
        sale_id__date_added__date__lte=end,
    )

    if user_company:
        qs = qs.filter(sale_id__company=user_company)

    return (
        qs.annotate(sale_date=TruncDate('sale_id__date_added'))
        .values(
            'sale_date',
            'product_id__code',
            'product_id__name',
            'product_id__category_id__name',
        )
        .annotate(total_quantity=Sum('qty'), total_revenue=Sum('total'))
        .order_by('-sale_date', 'product_id__code')
    )
