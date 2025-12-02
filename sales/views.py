import json
import base64
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum, F
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from core.utils import (
    generate_sale_code,
    get_date_range_from_request,
    get_report_queryset,
    get_user_company,
    serialize_receipt_items,
)
from p_v_App.models import (
    CashMovement,
    CashRegisterSession,
    Estoque,
    Pedido,
    PedidoItem,
    PedidoComboItem,
    PedidoPayment,
    Products,
    Sales,
    SalePayment,
    SaleComboItem,
    TableOrder,
    salesItems,
)
from debts.models import Debt
from clients.models import Client
from debts.models import Debt
from sales.forms import CashCloseForm, CashMovementForm, CashOpenForm
from sales.utils import (
    allocate_payments,
    generate_cash_report_pdf,
    get_open_cash_session,
    get_primary_payment_method,
    parse_payment_entries,
    payment_summary_for_sale,
    register_sale_payments,
    VALID_PAYMENT_METHODS,
    trigger_auto_print,
)


def _generate_unique_code(company):
    return generate_sale_code(company, [Pedido.objects.filter(company=company)])


@login_required
def pos(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    cash_session = get_open_cash_session(user_company)

    estoques = (
        Estoque.objects.filter(
            status=1,
            company=user_company,
            produto__status=1,
            produto__is_combo=False,
        )
        .select_related('produto')
        .order_by('produto__name')
    )

    combo_products = (
        Products.objects.filter(company=user_company, status=1, is_combo=True)
        .prefetch_related('combo_items__component')
        .order_by('name')
    )

    component_ids = set()
    for combo in combo_products:
        for item in combo.combo_items.all():
            component_ids.add(item.component_id)

    component_stocks = {}
    if component_ids:
        component_stocks = {
            estoque.produto_id: estoque.quantidade
            for estoque in Estoque.objects.filter(
                company=user_company,
                produto_id__in=component_ids,
            )
        }

    product_json = []
    for estoque in estoques:
        product = estoque.produto
        product_json.append(
            {
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'estoque': estoque.quantidade,
                'code': product.code,
                'codigo_barras': getattr(product, 'codigo_barras', product.code),
                'barcode': getattr(product, 'barcode', product.code),
                'product_code': product.code,
                'is_combo': False,
                'combo_total_quantity': None,
                'combo_max_flavors': None,
                'combo_items': [],
            }
        )

    for combo in combo_products:
        combo_items_payload = []
        available_options = []
        for item in combo.combo_items.all():
            component = item.component
            stock_qty = component_stocks.get(component.id, 0)
            try:
                quantity_value = float(item.quantity)
            except (TypeError, ValueError):
                quantity_value = 0.0
            if quantity_value > 0:
                available_options.append(
                    stock_qty / quantity_value if quantity_value else 0
                )
            combo_items_payload.append(
                {
                    'component_id': component.id,
                    'name': component.name,
                    'code': component.code,
                    'quantity': quantity_value,
                    'stock': stock_qty,
                }
            )

        available_quantity = None
        if available_options:
            try:
                available_quantity = int(min(available_options))
            except (ValueError, TypeError):
                available_quantity = None

        total_quantity = (
            float(combo.combo_total_quantity)
            if combo.combo_total_quantity is not None
            else None
        )

        product_json.append(
            {
                'id': combo.id,
                'name': combo.name,
                'price': float(combo.price),
                'estoque': available_quantity,
                'code': combo.code,
                'codigo_barras': getattr(combo, 'codigo_barras', combo.code),
                'barcode': getattr(combo, 'barcode', combo.code),
                'product_code': combo.code,
                'is_combo': True,
                'combo_total_quantity': total_quantity,
                'combo_max_flavors': combo.combo_max_flavors,
                'combo_items': combo_items_payload,
            }
        )

    context = {
        'page_title': 'Ponto de Venda',
        'products': estoques,
        'combo_products': combo_products,
        'product_json': json.dumps(product_json),
        'cash_session_open': bool(cash_session),
        'cash_session': cash_session,
        'clients': Client.objects.filter(company=user_company).order_by('name'),
    }
    return render(request, 'sales/pos.html', context)


@login_required
def checkout_modal(request):
    grand_total = request.GET.get('grand_total', 0)
    company = get_user_company(request)
    if not company:
        messages.error(request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    clients = Client.objects.filter(company=company).order_by('name')
    return render(
        request,
        'sales/checkout.html',
        {'grand_total': grand_total, 'clients': clients},
    )


@login_required
def save_pos(request):
    resp = {'status': 'failed', 'msg': ''}
    data = request.POST
    sale_type = data.get('type', 'venda')

    user_company = get_user_company(request)
    if not user_company:
        resp['msg'] = 'Usuário não está associado a nenhuma empresa.'
        return JsonResponse(resp)

    auto_open_print = getattr(user_company, 'auto_open_print', True)
    auto_print_flag = '1' if auto_open_print else '0'

    if not get_open_cash_session(user_company):
        resp['msg'] = 'Abra o caixa para registrar vendas no PDV.'
        return JsonResponse(resp)

    code = _generate_unique_code(user_company)
    combo_configs = data.getlist('combo_config[]')
    client = None
    client_id = data.get('client_id')
    if client_id not in (None, '', 'null'):
        try:
            client = Client.objects.get(pk=int(client_id), company=user_company)
        except (Client.DoesNotExist, ValueError):
            resp['msg'] = 'Cliente inválido informado.'
            return JsonResponse(resp)

    def resolve_combo_components(product, raw_config, combo_qty):
        if not product.is_combo:
            return []

        try:
            qty_value = Decimal(str(combo_qty))
        except (InvalidOperation, ValueError):
            raise ValueError('Quantidade inválida para o combo.')

        try:
            config_entries = json.loads(raw_config) if raw_config else []
        except json.JSONDecodeError:
            raise ValueError('Não foi possível interpretar os itens do combo.')

        combo_items = list(
            product.combo_items.select_related('component')
        )
        if not combo_items:
            raise ValueError(
                'Configure os componentes do combo antes de realizar a venda.'
            )

        if not config_entries:
            config_entries = [
                {
                    'component_id': item.component_id,
                    'quantity': float(item.quantity),
                }
                for item in combo_items
                if item.quantity and float(item.quantity) > 0
            ]

        allowed_components = {item.component_id: item for item in combo_items}
        aggregated = {}
        total_per_combo = Decimal('0')
        active_flavors = 0

        for entry in config_entries:
            component_id = entry.get('component_id') or entry.get('id')
            if component_id in (None, ''):
                continue
            try:
                component_id = int(component_id)
            except (TypeError, ValueError):
                raise ValueError('Item inválido informado para o combo.')

            if component_id not in allowed_components:
                raise ValueError(
                    'Um dos itens informados não pertence a este combo.')

            try:
                per_combo_qty = Decimal(str(entry.get('quantity', 0)))
            except (InvalidOperation, ValueError):
                raise ValueError(
                    'Quantidade inválida para um dos componentes do combo.')

            if per_combo_qty < 0:
                raise ValueError(
                    'Quantidade do componente do combo não pode ser negativa.')

            if per_combo_qty > 0:
                active_flavors += 1
            total_per_combo += per_combo_qty

            payload = aggregated.setdefault(
                component_id,
                {'item': allowed_components[component_id],
                    'per_combo': Decimal('0')},
            )
            payload['per_combo'] += per_combo_qty

        if not aggregated:
            raise ValueError('Informe os componentes consumidos pelo combo.')

        max_flavors = product.combo_max_flavors or 0
        if max_flavors and active_flavors > max_flavors:
            raise ValueError(
                'A quantidade de sabores selecionados excede o limite configurado para este combo.'
            )

        if product.combo_total_quantity is not None:
            expected = Decimal(str(product.combo_total_quantity))
            if expected > 0 and abs(total_per_combo - expected) > Decimal('0.0001'):
                raise ValueError(
                    f'A soma das quantidades dos componentes deve totalizar {expected}.'
                )

        resolved = []
        for payload in aggregated.values():
            total_quantity = payload['per_combo'] * qty_value
            if total_quantity <= 0:
                continue
            resolved.append(
                {
                    'component': payload['item'].component,
                    'total_quantity': total_quantity,
                }
            )

        if not resolved:
            raise ValueError('Informe os componentes consumidos pelo combo.')

        return resolved

    try:
        sub_total_value = Decimal(str(data.get('sub_total', 0) or 0))
        tax_amount_value = Decimal(str(data.get('tax_amount', 0) or 0))
        discount_value = Decimal(str(data.get('discount_total', 0) or 0))
        delivery_value = Decimal(
            str(data.get('taxa_entrega', data.get('delivery_fee', 0)) or 0))
    except InvalidOperation:
        resp['msg'] = 'Valores monetários inválidos informados.'
        return JsonResponse(resp)

    if delivery_value < Decimal('0'):
        delivery_value = Decimal('0')

    if discount_value < Decimal('0'):
        discount_value = Decimal('0')

    base_for_discount = sub_total_value + \
        tax_amount_value + max(delivery_value, Decimal('0'))
    if discount_value > base_for_discount:
        discount_value = base_for_discount

    discount_reason = (data.get('discount_reason') or '').strip()
    if len(discount_reason) > 255:
        discount_reason = discount_reason[:255]
    if discount_value > Decimal('0') and not discount_reason:
        resp['msg'] = 'Informe o motivo do desconto aplicado.'
        return JsonResponse(resp)
    if discount_value <= Decimal('0'):
        discount_reason = ''

    grand_total_value = sub_total_value + \
        tax_amount_value + delivery_value - discount_value
    if grand_total_value < Decimal('0'):
        grand_total_value = Decimal('0')

    register_debt = sale_type == 'venda' and data.get('register_debt') == '1'
    if register_debt and client is None:
        resp['msg'] = 'Selecione um cliente para registrar o débito.'
        return JsonResponse(resp)

    if sale_type == 'pedido':
        try:
            payment_methods = data.getlist('payment_method[]')
            payment_amounts = data.getlist('payment_amount[]')

            tendered_total = Decimal(str(data.get('tendered_amount', 0) or 0))
            change_total = Decimal(str(data.get('amount_change', 0) or 0))
            primary_method = data.get('forma_pagamento', 'PIX')

            if payment_methods:
                payment_entries = parse_payment_entries(
                    payment_methods, payment_amounts)
                allocations, tendered_total, change_total = allocate_payments(
                    grand_total_value, payment_entries
                )
                primary_method = get_primary_payment_method(allocations)
            else:
                if tendered_total < grand_total_value:
                    resp['msg'] = 'O valor pago é menor que o valor a pagar'
                    return JsonResponse(resp)
                change_total = tendered_total - grand_total_value
                allocations = [
                    {
                        'method': primary_method,
                        'tendered': tendered_total,
                        'applied': grand_total_value,
                        'change': change_total if change_total > Decimal('0') else Decimal('0'),
                    }
                ]
        except ValueError as exc:
            resp['msg'] = str(exc)
            return JsonResponse(resp)
        except Exception as exc:  # noqa: BLE001
            resp['msg'] = f'Erro ao processar pagamento: {exc}'
            return JsonResponse(resp)

        try:
            with transaction.atomic():
                pedido = Pedido.objects.create(
                    code=code,
                    sub_total=float(sub_total_value),
                    tax=float(data.get('tax', 0) or 0),
                    tax_amount=float(tax_amount_value),
                    grand_total=float(grand_total_value),
                    tendered_amount=float(tendered_total),
                    amount_change=float(change_total),
                    forma_pagamento=primary_method,
                    customer_name=data.get('customer_name', ''),
                    client=client,
                    endereco_entrega=data.get('endereco_entrega', ''),
                    taxa_entrega=float(delivery_value),
                    discount_total=float(discount_value),
                    discount_reason=discount_reason,
                    status='pendente',
                    company=user_company,
                )

                for idx, prod_id in enumerate(data.getlist('product_id[]')):
                    product = Products.objects.get(
                        id=prod_id, company=user_company)
                    qty_raw = data.getlist('qty[]')[idx]
                    try:
                        qty_decimal = Decimal(str(qty_raw))
                    except (InvalidOperation, ValueError):
                        raise ValueError(
                            'Quantidade inválida informada para um dos itens.')
                    price = float(data.getlist('price[]')[idx])
                    pedido_item = PedidoItem.objects.create(
                        pedido=pedido,
                        product=product,
                        qty=float(qty_decimal),
                        price=price,
                        total=float(qty_decimal) * price,
                    )

                    if product.is_combo:
                        raw_config = combo_configs[idx] if idx < len(
                            combo_configs) else ''
                        combo_components = resolve_combo_components(
                            product, raw_config, qty_decimal
                        )
                        PedidoComboItem.objects.filter(
                            pedido_item=pedido_item).delete()
                        for component in combo_components:
                            PedidoComboItem.objects.create(
                            pedido_item=pedido_item,
                            component=component['component'],
                            quantity=component['total_quantity'],
                        )

                for allocation in allocations:
                    PedidoPayment.objects.create(
                        company=user_company,
                        pedido=pedido,
                        method=allocation['method'],
                        tendered_amount=allocation['tendered'],
                        applied_amount=allocation['applied'],
                        change_amount=allocation['change'],
                        recorded_by=request.user,
                    )

                print_status = False
                print_message = 'Impressao automatica desativada para esta empresa.'
                if auto_open_print:
                    try:
                        print_status, print_message = trigger_auto_print(pedido)
                    except Exception as print_exc:  # noqa: BLE001
                        print_status, print_message = False, f'Falha ao acionar impressao: {print_exc}'

                resp = {
                    'status': 'success',
                    'sale_id': pedido.id,
                    'type': 'pedido',
                    'receipt_url': (
                        reverse('receipt-modal') + f'?id={pedido.id}&auto_print={auto_print_flag}'
                        if auto_open_print else ''
                    ),
                    'print_status': 'success' if print_status else 'skipped',
                    'print_message': print_message,
                }
        except Exception as exc:
            resp['msg'] = f'Erro ao processar pedido: {exc}'
        return JsonResponse(resp)

    try:
        payment_methods = data.getlist('payment_method[]')
        payment_amounts = data.getlist('payment_amount[]')
        if not payment_methods and not payment_amounts:
            payment_methods = [data.get('forma_pagamento', 'PIX')]
            fallback_amount = data.get('tendered_amount', None)
            if fallback_amount in (None, ''):
                fallback_amount = '0' if register_debt else str(grand_total_value)
            payment_amounts = [fallback_amount]

        has_positive_payment = False
        for raw_amount in payment_amounts:
            try:
                if Decimal(str(raw_amount)) > Decimal('0'):
                    has_positive_payment = True
                    break
            except (InvalidOperation, ValueError, TypeError):
                continue

        if register_debt and not has_positive_payment:
            payment_entries = []
            allocations = []
            tendered_total = Decimal('0')
            change_total = Decimal('0')
            primary_method = 'MULTI'
        else:
            try:
                payment_entries = parse_payment_entries(
                    payment_methods, payment_amounts, allow_empty=register_debt
                )
                allocations, tendered_total, change_total = allocate_payments(
                    grand_total_value, payment_entries, allow_partial=register_debt
                )
                primary_method = get_primary_payment_method(allocations)
            except ValueError as exc:
                resp['msg'] = str(exc)
                return JsonResponse(resp)

        debt_created = False
        debt_amount = Decimal('0')
        with transaction.atomic():
            venda = Sales.objects.create(
                code=code,
                sub_total=float(sub_total_value),
                tax=float(data.get('tax', 0) or 0),
                tax_amount=float(tax_amount_value),
                grand_total=float(grand_total_value),
                tendered_amount=float(tendered_total),
                amount_change=float(change_total),
                forma_pagamento=primary_method,
                customer_name=data.get('customer_name', ''),
                client=client,
                endereco_entrega=data.get('endereco_entrega', ''),
                delivery_fee=float(delivery_value),
                discount_total=float(discount_value),
                discount_reason=discount_reason,
                type='venda',
                venda_a_prazo=register_debt,
                company=user_company,
            )

            for idx, prod_id in enumerate(data.getlist('product_id[]')):
                product = Products.objects.get(
                    id=prod_id, company=user_company)
                qty_raw = data.getlist('qty[]')[idx]
                try:
                    qty_decimal = Decimal(str(qty_raw))
                except (InvalidOperation, ValueError):
                    raise ValueError(
                        'Quantidade inválida informada para um dos itens.')
                price = float(data.getlist('price[]')[idx])
                sale_item = salesItems.objects.create(
                    sale_id=venda,
                    product_id=product,
                    qty=float(qty_decimal),
                    price=price,
                    total=float(qty_decimal) * price,
                )

                if product.is_combo:
                    raw_config = combo_configs[idx] if idx < len(
                        combo_configs) else ''
                    combo_components = resolve_combo_components(
                        product, raw_config, qty_decimal
                    )
                    SaleComboItem.objects.filter(sale_item=sale_item).delete()
                    for component in combo_components:
                        SaleComboItem.objects.create(
                            sale_item=sale_item,
                            component=component['component'],
                            quantity=component['total_quantity'],
                        )
                        try:
                            estoque_item = Estoque.objects.get(
                                produto=component['component'],
                                company=user_company,
                            )
                            estoque_item.quantidade -= float(
                                component['total_quantity'])
                            estoque_item.save(update_fields=['quantidade'])
                        except Estoque.DoesNotExist:
                            pass
                else:
                    try:
                        estoque_item = Estoque.objects.get(
                            produto=product, company=user_company
                        )
                        estoque_item.quantidade -= float(qty_decimal)
                        estoque_item.save(update_fields=['quantidade'])
                    except Estoque.DoesNotExist:
                        pass

            register_sale_payments(venda, allocations, request.user)

            paid_total = sum(
                (
                    allocation.get('applied') or Decimal('0')
                    for allocation in allocations
                ),
                start=Decimal('0'),
            )
            try:
                grand_total_dec = (
                    grand_total_value if isinstance(
                        grand_total_value, Decimal) else Decimal(str(grand_total_value))
                )
                paid_total_dec = (
                    paid_total if isinstance(paid_total, Decimal) else Decimal(str(paid_total))
                )
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError('NÇœo foi possÇðvel calcular o saldo a prazo.')

            remaining_due = (grand_total_dec - paid_total_dec).quantize(Decimal('0.01'))
            if remaining_due < Decimal('0'):
                remaining_due = Decimal('0')
            if register_debt and remaining_due > Decimal('0.009'):
                total_display = grand_total_dec.quantize(Decimal('0.01'))
                paid_display = paid_total_dec.quantize(Decimal('0.01'))
                Debt.objects.create(
                    company=user_company,
                    client=client,
                    sale=venda,
                    amount=remaining_due,
                    description=(
                        f'Venda #{venda.code} - pendência de pagamento. '
                        f'Total: R$ {total_display}; pago: R$ {paid_display}; saldo: R$ {remaining_due}.'
                    ),
                    status=Debt.Status.OPEN,
                )
                debt_created = True
                debt_amount = remaining_due
            print_status = False
            print_message = 'Impressao automatica desativada para esta empresa.'
            if auto_open_print:
                try:
                    print_status, print_message = trigger_auto_print(venda)
                except Exception as print_exc:  # noqa: BLE001
                    print_status, print_message = False, f'Falha ao acionar impressao: {print_exc}'

            resp = {
                'status': 'success',
                'sale_id': venda.id,
                'type': 'venda',
                'receipt_url': (
                    reverse('receipt-modal') + f'?id={venda.id}&auto_print={auto_print_flag}'
                    if auto_open_print else ''
                ),
                'print_status': 'success' if print_status else 'skipped',
                'print_message': print_message,
                'register_debt': register_debt,
                'debt_created': debt_created,
                'debt_amount': str(debt_amount.quantize(Decimal('0.01'))) if debt_amount else '0.00',
            }
    except Exception as exc:
        resp['msg'] = f'Erro ao processar venda: {exc}'
    return JsonResponse(resp)


@login_required
def salesList(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    payment_method = request.GET.get('payment_method', '').strip()
    page = request.GET.get('page', 1)

    today = timezone.now().date()
    default_start = today - timedelta(days=30)

    try:
        filter_start = datetime.strptime(
            start_date, '%Y-%m-%d').date() if start_date else default_start
    except ValueError:
        filter_start = default_start

    try:
        filter_end = datetime.strptime(
            end_date, '%Y-%m-%d').date() if end_date else today
    except ValueError:
        filter_end = today

    base_qs = Sales.objects.filter(
        (Q(type__in=['venda', 'pedido']) | Q(type__istartswith='Mesa')),
        company=user_company,
        date_added__date__gte=filter_start,
        date_added__date__lte=filter_end,
    )

    if payment_method:
        base_qs = base_qs.filter(forma_pagamento=payment_method)

    sales_qs = (
        base_qs.select_related(
            'table', 'table_order__table', 'table_order__waiter')
        .prefetch_related('payments')
        .order_by('-date_added')
    )

    paginator = Paginator(sales_qs, 15)
    try:
        sales_paginated = paginator.page(page)
    except PageNotAnInteger:
        sales_paginated = paginator.page(1)
    except EmptyPage:
        sales_paginated = paginator.page(paginator.num_pages)

    sale_data = []
    for sale in sales_paginated:
        payment_details = payment_summary_for_sale(sale)
        record = {
            'id': sale.id,
            'code': sale.code,
            'date_added': sale.date_added,
            'grand_total': sale.grand_total,
            'forma_pagamento': sale.forma_pagamento,
            'forma_pagamento_label': dict(Sales.FORMA_PAGAMENTO_CHOICES).get(
                sale.forma_pagamento, sale.forma_pagamento
            ),
            'customer_name': sale.customer_name,
            'table_number': sale.table.number if sale.table else None,
            'table_id': sale.table_id,
            'table_order_id': sale.table_order_id,
            'waiter_name': sale.table_order.waiter_name if sale.table_order else '',
            'is_table_sale': (sale.type or '').lower().startswith('mesa'),
            'tendered_amount': sale.tendered_amount,
            'amount_change': sale.amount_change,
            'payments': payment_details,
            'delivery_fee': sale.delivery_fee,
            'discount_total': sale.discount_total,
            'discount_reason': sale.discount_reason,
        }

        items = list(
            salesItems.objects.filter(sale_id=sale)
            .select_related('product_id')
            .prefetch_related('combo_components__component')
        )
        record['items'] = items
        record['item_count'] = len(items)
        total_cost = sum(
            item.qty * (item.product_id.custo or 0)
            for item in items
        )
        record['total_cost'] = total_cost
        record['profit'] = float(sale.grand_total) - float(total_cost)
        record['tax_amount'] = format(float(sale.tax_amount or 0), '.2f')
        sale_data.append(record)

    stats_sales = base_qs.aggregate(
        total_sales=Count('id'),
        total_revenue=Sum('grand_total'),
        total_tax=Sum('tax_amount'),
        total_delivery=Sum('delivery_fee'),
    )

    period_cost = 0
    period_profit = 0
    for sale in base_qs.prefetch_related('salesitems_set__product_id'):
        sale_cost = sum(
            item.qty * (item.product_id.custo or 0) for item in sale.salesitems_set.all()
        )
        period_cost += sale_cost
        period_profit += float(sale.grand_total) - sale_cost

    payment_methods = (
        base_qs.values_list('forma_pagamento', flat=True).distinct().order_by(
            'forma_pagamento')
    )

    context = {
        'page_title': 'Transações de Vendas',
        'sale_data': sale_data,
        'sales_paginated': sales_paginated,
        'current': 'sales-page',
        'start_date': filter_start.strftime('%Y-%m-%d'),
        'end_date': filter_end.strftime('%Y-%m-%d'),
        'payment_method': payment_method,
        'payment_methods': payment_methods,
        'total_sales': stats_sales.get('total_sales') or 0,
        'total_revenue': float(stats_sales.get('total_revenue') or 0),
        'total_cost': period_cost,
        'total_profit': period_profit,
        'total_tax': float(stats_sales.get('total_tax') or 0),
        'total_delivery_fee': float(stats_sales.get('total_delivery') or 0),
    }
    return render(request, 'sales/sales.html', context)


@login_required
def receipt(request):
    sale_id = request.GET.get('id')
    auto_print = request.GET.get('auto_print') == '1'
    sale = (
        Sales.objects.select_related(
            'table', 'table_order__table', 'table_order__waiter')
        .filter(id=sale_id)
        .first()
    )

    if not sale:
        return render(request, 'core/receipt_not_found.html', status=404)

    payment_details = payment_summary_for_sale(sale)

    if sale.table_order_id:
        order = sale.table_order
        items = order.items.select_related('product').order_by('added_at')
        return render(
            request,
            'tables/mesa_receipt.html',
            {
                'sale': sale,
                'order': order,
                'items': items,
                'payments': payment_details,
                'auto_print': auto_print,
            },
        )

    items_qs = (
        salesItems.objects.filter(sale_id=sale)
        .select_related('product_id')
        .prefetch_related('combo_components__component')
        .order_by('id')
    )
    sale_type = (sale.type or '').lower()

    if sale_type == 'pedido':
        context = {
            'title': 'Recibo de Pedido',
            'record': sale,
            'items': serialize_receipt_items(items_qs),
            'is_sale_record': True,
            'delivery_fee': sale.delivery_fee or 0,
            'customer_address': sale.endereco_entrega,
            'auto_print': auto_print,
            'payments': payment_details,
        }
        return render(request, 'orders/receipt_pedido.html', context)

    context = {
        'title': 'Recibo de Caixa',
        'sale': sale,
        'items': serialize_receipt_items(items_qs),
        'payments': payment_details,
        'auto_print': auto_print,
    }
    return render(request, 'sales/receipt_caixa.html', context)


@login_required
def cashier_dashboard(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    open_session = get_open_cash_session(user_company)
    open_form = CashOpenForm()
    movement_form = CashMovementForm()
    close_form = CashCloseForm()
    session_movements = []
    payment_breakdown = []
    manual_movements = []
    open_tables_count = 0

    entries_total = Decimal('0')
    exits_total = Decimal('0')
    expected_balance = Decimal('0')

    if open_session:
        movement_form = CashMovementForm(
            initial={'type': CashMovement.Type.ENTRY,
                     'payment_method': 'DINHEIRO'}
        )
        close_form = CashCloseForm(
            initial={'closing_amount': open_session.expected_balance()}
        )
        session_movements = (
            open_session.movements.select_related('recorded_by', 'sale')
            .order_by('-recorded_at')
        )
        manual_movements = [
            movement for movement in session_movements if movement.sale_id is None]
        sale_ids = (
            movement.sale_id
            for movement in session_movements
            if movement.sale_id is not None
        )
        sale_ids = list(dict.fromkeys(sale_ids))
        if sale_ids:
            payment_breakdown = (
                SalePayment.objects.filter(sale_id__in=sale_ids)
                .values('method')
                .annotate(
                    total_applied=Sum('applied_amount'),
                    total_tendered=Sum('tendered_amount'),
                    total_change=Sum('change_amount'),
                )
                .order_by('method')
            )
        method_labels = dict(Sales.FORMA_PAGAMENTO_CHOICES)
        payment_breakdown = [
            {
                'method': method_labels.get(item['method'], item['method']),
                'method_code': item['method'],
                'total_applied': item['total_applied'],
                'total_tendered': item['total_tendered'],
                'total_change': item['total_change'],
            }
            for item in payment_breakdown
        ]
        entries_total = open_session.total_entries()
        exits_total = open_session.total_exits()
        expected_balance = open_session.expected_balance()
        open_tables_count = TableOrder.objects.filter(
            company=user_company, status=TableOrder.Status.OPEN
        ).count()

    history_date_str = request.GET.get('history_date', '').strip()
    history_date = None
    if history_date_str:
        try:
            history_date = datetime.strptime(
                history_date_str, '%Y-%m-%d').date()
        except ValueError:
            history_date = None

    session_history_qs = (
        CashRegisterSession.objects.filter(company=user_company)
        .order_by('-opened_at')
        .select_related('opened_by', 'closed_by')
    )
    if history_date:
        session_history_qs = session_history_qs.filter(
            opened_at__date=history_date)

    history_total_count = session_history_qs.count()
    if history_date:
        session_history = list(session_history_qs)
    else:
        session_history = list(session_history_qs[:5])

    context = {
        'current': 'cashier',
        'open_session': open_session,
        'open_form': open_form,
        'movement_form': movement_form,
        'close_form': close_form,
        'movements': session_movements,
        'manual_movements': manual_movements,
        'payment_breakdown': payment_breakdown,
        'session_history': session_history,
        'entries_total': entries_total,
        'exits_total': exits_total,
        'expected_balance': expected_balance,
        'open_tables_count': open_tables_count,
        'history_date': history_date_str,
        'history_filter_active': bool(history_date),
        'history_total_count': history_total_count,
    }
    return render(request, 'sales/cashier.html', context)


@login_required
def open_cash_session(request):
    if request.method != 'POST':
        messages.error(request, 'Método inválido para abertura de caixa.')
        return redirect('cashier')

    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    if get_open_cash_session(user_company):
        messages.warning(request, 'Já existe um caixa aberto nesta empresa.')
        return redirect('cashier')

    form = CashOpenForm(request.POST)
    if form.is_valid():
        CashRegisterSession.objects.create(
            company=user_company,
            opened_by=request.user,
            opening_amount=form.cleaned_data['opening_amount'],
            opening_note=form.cleaned_data['opening_note'],
            status=CashRegisterSession.Status.OPEN,
            opened_at=timezone.now(),
        )
        messages.success(request, 'Caixa aberto com sucesso.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('cashier')


@login_required
def register_cash_movement(request):
    if request.method != 'POST':
        messages.error(
            request, 'Método inválido para registrar movimentação de caixa.')
        return redirect('cashier')

    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    session = get_open_cash_session(user_company)
    if not session:
        messages.error(request, 'Não há caixa aberto no momento.')
        return redirect('cashier')

    form = CashMovementForm(request.POST)
    if form.is_valid():
        movement = CashMovement.objects.create(
            company=user_company,
            session=session,
            type=form.cleaned_data['type'],
            amount=form.cleaned_data['amount'],
            payment_method=form.cleaned_data['payment_method'],
            description=form.cleaned_data['description'],
            note=form.cleaned_data['note'],
            recorded_by=request.user,
            recorded_at=timezone.now(),
        )
        if movement.type == CashMovement.Type.ENTRY:
            messages.success(request, 'Entrada registrada no caixa.')
        else:
            messages.success(request, 'Saída registrada no caixa.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('cashier')


@login_required
def close_cash_session(request):
    if request.method != 'POST':
        messages.error(request, 'Método inválido para fechamento de caixa.')
        return redirect('cashier')

    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    session = get_open_cash_session(user_company)
    if not session:
        messages.error(request, 'Não há caixa aberto para ser fechado.')
        return redirect('cashier')

    if TableOrder.objects.filter(company=user_company, status=TableOrder.Status.OPEN).exists():
        messages.error(
            request,
            'Não é possível fechar o caixa enquanto houver comandas abertas. Finalize as comandas antes de encerrar o caixa.',
        )
        return redirect('cashier')

    form = CashCloseForm(request.POST)
    if not form.is_valid():
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
        return redirect('cashier')

    with transaction.atomic():
        session.status = CashRegisterSession.Status.CLOSED
        session.closed_at = timezone.now()
        session.closed_by = request.user
        session.closing_amount = form.cleaned_data['closing_amount']
        session.closing_note = form.cleaned_data['closing_note']
        session.save(update_fields=[
                     'status', 'closed_at', 'closed_by', 'closing_amount', 'closing_note'])

    pdf_bytes = generate_cash_report_pdf(session)
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

    context = {
        'current': 'cashier',
        'session': session,
        'pdf_base64': pdf_base64,
        'file_name': f'fechamento-caixa-{session.id}.pdf',
    }
    return render(request, 'sales/cashier_close_report.html', context)


@login_required
def cashier_session_report(request, session_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    session = get_object_or_404(
        CashRegisterSession, pk=session_id, company=user_company)
    pdf_bytes = generate_cash_report_pdf(session)
    download_flag = str(request.GET.get('download', '')).lower()
    should_download = download_flag in {'1', 'true', 'yes', 'download'}
    filename = f'fechamento-caixa-{session.id}.pdf'

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    disposition = 'attachment' if should_download else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


@login_required
def delete_sale(request):
    resp = {'status': 'failed', 'msg': ''}
    sale_id = request.POST.get('id')
    user_company = get_user_company(request)
    try:
        sale = Sales.objects.get(pk=sale_id, company=user_company)
    except Sales.DoesNotExist:
        resp['msg'] = 'Venda não encontrada.'
        return JsonResponse(resp)

    sale.delete()
    messages.success(request, 'Registro de venda deletado com sucesso.')
    resp['status'] = 'success'
    return JsonResponse(resp)


@login_required
def sales_report(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    start, end = get_date_range_from_request(request)

    items_qs = salesItems.objects.filter(
        (Q(sale_id__type__in=['venda', 'pedido'])
         | Q(sale_id__type__istartswith='Mesa')),
        sale_id__company=user_company,
        sale_id__date_added__date__gte=start,
        sale_id__date_added__date__lte=end,
    )
    sales_qs = Sales.objects.filter(
        (Q(type__in=['venda', 'pedido']) | Q(type__istartswith='Mesa')),
        company=user_company,
        date_added__date__gte=start,
        date_added__date__lte=end,
    )

    cash_exits_agg = (
        CashMovement.objects.filter(
            company=user_company,
            type=CashMovement.Type.EXIT,
            recorded_at__date__gte=start,
            recorded_at__date__lte=end,
        ).aggregate(total=Sum('amount'))
    )

    sales_aggregates = sales_qs.aggregate(
        total_revenue=Sum('grand_total'),
        total_tax=Sum('tax_amount'),
        total_discount=Sum('discount_total'),
        total_delivery=Sum('delivery_fee'),
    )
    items_cost_agg = items_qs.aggregate(
        total_cost=Sum(F('qty') * F('product_id__custo'))
    )
    total_revenue_dec = Decimal(str(sales_aggregates.get('total_revenue') or 0))
    total_cost_dec = Decimal(str(items_cost_agg.get('total_cost') or 0))
    totals = {
        'total_tx': sales_qs.count(),
        'total_revenue': float(total_revenue_dec),
        'total_quantity': items_qs.aggregate(total_quantity=Sum('qty'))['total_quantity'] or 0,
        'total_discount': float(sales_aggregates.get('total_discount') or 0),
        'total_delivery_fee': float(sales_aggregates.get('total_delivery') or 0),
        'total_tax': float(sales_aggregates.get('total_tax') or 0),
        'total_cash_exits': float(cash_exits_agg.get('total') or 0),
        'total_cost': float(total_cost_dec),
        'total_profit': float(total_revenue_dec - total_cost_dec),
    }
    totals['total_average_ticket'] = (
        totals['total_revenue'] /
        totals['total_tx'] if totals['total_tx'] else 0
    )

    raw_data = (
        items_qs.annotate(sale_date=TruncDate('sale_id__date_added'))
        .values(
            'sale_date',
            'product_id__code',
            'product_id__name',
            'product_id__category_id__name',
        )
        .annotate(total_quantity=Sum('qty'), total_revenue=Sum('total'))
        .order_by('-sale_date', 'product_id__code')
    )
    report_data = []
    for rec in raw_data:
        rec['total_quantity'] = round(rec.get('total_quantity') or 0, 2)
        report_data.append(rec)

    payment_summary = [
        {
            'forma_pagamento': entry['forma_pagamento'] or 'Não especificado',
            'count': entry['count'] or 0,
            'total_value': entry['total_value'] or 0,
        }
        for entry in (
            sales_qs.values('forma_pagamento')
            .annotate(count=Count('id'), total_value=Sum('grand_total'))
            .order_by('forma_pagamento')
        )
    ]

    payment_by_day = (
        sales_qs.annotate(sale_date=TruncDate('date_added'))
        .values('sale_date', 'forma_pagamento')
        .annotate(count=Count('id'), total_value=Sum('grand_total'))
        .order_by('-sale_date', 'forma_pagamento')
    )

    debt_pending_qs = Debt.objects.filter(
        company=user_company,
        status=Debt.Status.OPEN,
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    debt_paid_qs = Debt.objects.filter(
        company=user_company,
        status=Debt.Status.PAID,
        paid_at__date__gte=start,
        paid_at__date__lte=end,
    )
    debt_cards = {
        'pending': {
            'total': float(
                Debt.aggregate_total(
                    company=user_company,
                    status=Debt.Status.OPEN,
                    created_at__date__gte=start,
                    created_at__date__lte=end,
                )
            ),
            'clients': (
                debt_pending_qs.exclude(client__isnull=True)
                .values('client_id')
                .distinct()
                .count()
            ),
            'overdue': debt_pending_qs.filter(due_date__lt=timezone.localdate()).count(),
        },
        'paid': {
            'total': float(
                Debt.aggregate_total(
                    company=user_company,
                    status=Debt.Status.PAID,
                    paid_at__date__gte=start,
                    paid_at__date__lte=end,
                )
            ),
            'count': debt_paid_qs.count(),
        },
    }
    debt_cards['paid_plus_profit'] = float(
        Decimal(str(debt_cards['paid']['total'])) + Decimal(str(totals['total_profit']))
    )

    context = {
        'page_title': 'Relatório de Vendas por Produto',
        'start_date': start.strftime('%Y-%m-%d'),
        'end_date': end.strftime('%Y-%m-%d'),
        'totals': totals,
        'report_data': report_data,
        'current': 'sales_report',
        'payment_summary': payment_summary,
        'payment_by_day': payment_by_day,
        'debt_cards': debt_cards,
    }
    return render(request, 'sales/sales_report.html', context)


@login_required
def export_sales_report(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('sales_report')

    start, end = get_date_range_from_request(request)
    qs = get_report_queryset(start, end, user_company)

    wb = Workbook()
    ws = wb.active
    ws.title = 'Vendas por Produto'

    ws.append(['Data', 'Código', 'Produto',
              'Categoria', 'Quantidade', 'Receita'])
    for rec in qs:
        ws.append(
            [
                rec['sale_date'].strftime('%d/%m/%y'),
                rec['product_id__code'],
                rec['product_id__name'],
                rec['product_id__category_id__name'],
                float(rec['total_quantity'] or 0),
                float(rec['total_revenue'] or 0),
            ]
        )

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response[
        'Content-Disposition'
    ] = f'attachment; filename="sales_report_{user_company.name}_{start}_{end}.xlsx"'
    wb.save(response)
    return response
