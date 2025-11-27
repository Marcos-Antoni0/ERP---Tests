import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.utils import (
    generate_sale_code,
    get_user_company,
    serialize_receipt_items,
)
from p_v_App.models import (
    Estoque,
    Pedido,
    PedidoItem,
    PedidoComboItem,
    SaleComboItem,
    Sales,
    salesItems,
    PedidoPayment,
)
from sales.utils import get_primary_payment_method, register_sale_payments


@login_required
def pedidos(request):
    user_company = get_user_company(request)
    if user_company:
        pendentes = (
            Pedido.objects.filter(status='pendente', company=user_company)
            .order_by('-date_added')
        )
        em_rota = (
            Pedido.objects.filter(status='em_rota', company=user_company)
            .order_by('-date_added')
        )
        entregues = (
            Pedido.objects.filter(status='entregue', company=user_company)
            .order_by('-date_added')
        )
    else:
        pendentes = em_rota = entregues = Pedido.objects.none()

    context = {
        'pedidos_pendentes': pendentes,
        'pedidos_em_rota': em_rota,
        'pedidos_entregues': entregues,
        'page_title': 'Controle de Pedidos',
    }
    return render(request, 'orders/pedidos.html', context)


@login_required
def atualizar_status_pedido(request, id):
    if request.method != 'POST':
        messages.error(request, 'Método HTTP inválido.')
        return redirect('pedidos')

    user_company = get_user_company(request)
    pedido = get_object_or_404(Pedido, pk=id, company=user_company)

    status_flow = ['pendente', 'em_rota', 'entregue']
    try:
        current_idx = status_flow.index(pedido.status)
        if current_idx < len(status_flow) - 1:
            pedido.status = status_flow[current_idx + 1]
            pedido.save(update_fields=['status'])
            messages.success(
                request,
                f"Status do pedido #{pedido.code} atualizado para '{pedido.status}'.",
            )
        else:
            messages.info(request, 'Pedido já está com status final.')
    except ValueError:
        messages.error(request, 'Status atual do pedido inválido.')

    return redirect('pedidos')


@login_required
def finalizar_pedido(request, pedido_id):
    if request.method != 'POST':
        messages.error(request, 'Método HTTP inválido.')
        return redirect('pedidos')

    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('pedidos')

    pedido = get_object_or_404(
        Pedido, pk=pedido_id, status='entregue', company=user_company
    )

    pedido_payments = list(
        PedidoPayment.objects.filter(pedido=pedido).order_by('-recorded_at')
    )
    allocations = [
        {
            'method': payment.method,
            'tendered': Decimal(payment.tendered_amount),
            'applied': Decimal(payment.applied_amount),
            'change': Decimal(payment.change_amount),
        }
        for payment in pedido_payments
    ]
    if allocations:
        primary_method = get_primary_payment_method(allocations) or 'PIX'
        tendered_total = sum((alloc['tendered'] for alloc in allocations), Decimal('0'))
        change_total = sum((alloc['change'] for alloc in allocations), Decimal('0'))
    else:
        primary_method = pedido.forma_pagamento or 'PIX'
        tendered_total = Decimal(str(pedido.tendered_amount or 0))
        change_total = Decimal(str(pedido.amount_change or 0))
        allocations = [
            {
                'method': primary_method,
                'tendered': tendered_total,
                'applied': Decimal(str(pedido.grand_total or 0)),
                'change': change_total if change_total > Decimal('0') else Decimal('0'),
            }
        ]

    try:
        with transaction.atomic():
            sale_code = generate_sale_code(user_company)
            discount_reason = pedido.discount_reason if (
                pedido.discount_total or 0) > 0 else ''

            venda = Sales.objects.create(
                code=sale_code,
                sub_total=pedido.sub_total,
                tax=pedido.tax,
                tax_amount=pedido.tax_amount,
                grand_total=pedido.grand_total,
                tendered_amount=float(tendered_total),
                amount_change=float(change_total),
                forma_pagamento=primary_method,
                endereco_entrega=pedido.endereco_entrega,
                customer_name=pedido.customer_name,
                delivery_fee=pedido.taxa_entrega,
                discount_total=pedido.discount_total,
                discount_reason=discount_reason,
                type='pedido',
                company=user_company,
            )

            for item in PedidoItem.objects.filter(pedido=pedido).select_related('product'):
                sale_item = salesItems.objects.create(
                    sale_id=venda,
                    product_id=item.product,
                    qty=item.qty,
                    price=item.price,
                    total=item.total,
                )
                if item.product.is_combo:
                    combo_components = list(
                        PedidoComboItem.objects.filter(pedido_item=item)
                        .select_related('component')
                    )
                    for combo in combo_components:
                        SaleComboItem.objects.create(
                            sale_item=sale_item,
                            component=combo.component,
                            quantity=combo.quantity,
                        )
                        try:
                            estoque_item = Estoque.objects.get(
                                produto=combo.component,
                                company=user_company,
                            )
                            estoque_item.quantidade -= float(combo.quantity)
                            estoque_item.save(update_fields=['quantidade'])
                        except Estoque.DoesNotExist:
                            pass
                else:
                    try:
                        estoque_item = Estoque.objects.get(
                            produto=item.product, company=user_company)
                        estoque_item.quantidade -= item.qty
                        estoque_item.save(update_fields=['quantidade'])
                    except Estoque.DoesNotExist:
                        pass

            register_sale_payments(venda, allocations, request.user)
            PedidoItem.objects.filter(pedido=pedido).delete()
            pedido.delete()
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('pedidos')

    messages.success(request, 'Pedido convertido em venda com sucesso.')
    return redirect('pedidos')


@login_required
def delete_pedido(request):
    resp = {'status': 'failed', 'msg': ''}
    pedido_id = request.POST.get('id')
    user_company = get_user_company(request)
    if not user_company:
        resp['msg'] = 'Usuário não está associado a nenhuma empresa.'
        return HttpResponse(json.dumps(resp), content_type='application/json')

    try:
        pedido = Pedido.objects.get(pk=pedido_id, company=user_company)
    except Pedido.DoesNotExist:
        resp['msg'] = 'Pedido não encontrado.'
        return HttpResponse(json.dumps(resp), content_type='application/json')

    PedidoItem.objects.filter(pedido=pedido).delete()
    pedido.delete()
    resp['status'] = 'success'
    messages.success(request, 'Pedido deletado com sucesso.')
    return HttpResponse(json.dumps(resp), content_type='application/json')


@login_required
def view_pedido(request):
    pedido_id = request.GET.get('id')
    try:
        pedido_id = int(pedido_id)
    except (TypeError, ValueError):
        pedido_id = None

    user_company = get_user_company(request)
    pedido_qs = Pedido.objects.all()
    if user_company:
        pedido_qs = pedido_qs.filter(company=user_company)

    if not pedido_id:
        return render(request, 'core/receipt_not_found.html')

    pedido = pedido_qs.filter(pk=pedido_id).first()
    if not pedido:
        return render(request, 'core/receipt_not_found.html')

    items_qs = (
        PedidoItem.objects.filter(pedido=pedido)
        .select_related('product')
        .prefetch_related('combo_components__component')
        .order_by('id')
    )

    payments = [
        {
            'method': payment.get_method_display(),
            'method_code': payment.method,
            'tendered': float(payment.tendered_amount),
            'applied': float(payment.applied_amount),
            'change': float(payment.change_amount),
        }
        for payment in pedido.payments.all().order_by('-recorded_at')
    ]

    context = {
        'title': 'Recibo de Pedido',
        'record': pedido,
        'items': serialize_receipt_items(items_qs),
        'is_sale_record': False,
        'delivery_fee': pedido.taxa_entrega or 0,
        'customer_address': pedido.endereco_entrega,
        'payments': payments,
    }
    return render(request, 'orders/receipt_pedido.html', context)
