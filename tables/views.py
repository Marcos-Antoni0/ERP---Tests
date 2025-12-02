from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.utils import (
    create_sale_from_table_order,
    get_user_company,
    guard_tables_ready,
    reopen_table_order,
    table_models_ready,
)
from sales.utils import (
    allocate_payments,
    get_open_cash_session,
    get_primary_payment_method,
    parse_payment_entries,
    trigger_auto_print,
)
from p_v_App.models import Garcom, Products, Sales, Table, TableOrder, TableOrderItem
from tables.forms import (
    TableForm,
    TableOrderCloseForm,
    TableOrderForm,
    TableOrderItemForm,
)


@login_required
def mesas(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    cash_session_open = bool(get_open_cash_session(user_company))

    search_number = request.GET.get('table_number', '').strip()
    if search_number:
        try:
            number = int(search_number)
        except ValueError:
            messages.error(
                request, 'Informe apenas números ao buscar uma mesa.')
        else:
            if table_models_ready():
                table = Table.objects.filter(
                    company=user_company, number=number).first()
                if table:
                    return redirect('mesa-detalhe', table_id=table.id)
            messages.warning(request, f'Mesa {number} não encontrada.')

    tables_ready = table_models_ready()
    tables = []
    open_orders = []
    recent_orders = []

    if tables_ready:
        table_queryset = (
            Table.objects.filter(company=user_company)
            .select_related('waiter')
            .prefetch_related(
                Prefetch(
                    'orders',
                    queryset=TableOrder.objects.filter(company=user_company)
                    .order_by('-opened_at')
                    .select_related('waiter')
                    .prefetch_related('items__product'),
                )
            )
        )
        tables = list(table_queryset)

        for table in tables:
            table.open_order = next(
                (order for order in table.orders.all()
                 if order.status == TableOrder.Status.OPEN),
                None,
            )
            if table.open_order:
                open_orders.append(table.open_order)
            table.recent_orders = [
                order for order in table.orders.all() if order.status != TableOrder.Status.OPEN
            ][:3]

        open_orders.sort(key=lambda order: order.opened_at)

        recent_orders = list(
            TableOrder.objects.filter(company=user_company)
            .exclude(status=TableOrder.Status.OPEN)
            .select_related('table', 'waiter')
            .order_by('-opened_at')[:10]
        )

    available_products = (
        Products.objects.filter(company=user_company, status=1, is_combo=False)
        .order_by('name')
    )
    unavailable_products = (
        Products.objects.filter(company=user_company, status=0, is_combo=False)
        .order_by('name')
    )

    active_waiters_qs = Garcom.objects.none()
    if tables_ready:
        active_waiters_qs = Garcom.objects.filter(
            company=user_company, is_active=True).order_by('name')

    context = {
        'page_title': 'Mesas e Comandas',
        'tables': tables,
        'open_orders': open_orders,
        'recent_orders': recent_orders,
        'table_form': TableForm(company=user_company),
        'available_products': available_products,
        'unavailable_products': unavailable_products,
        'tables_ready': tables_ready,
        'active_waiters': active_waiters_qs,
        'has_waiters': tables_ready and active_waiters_qs.exists(),
        'cash_session_open': cash_session_open,
    }

    if not tables_ready:
        messages.warning(
            request,
            'Para usar o controle de mesas e comandas execute as migrações pendentes com "python manage.py migrate".',
        )

    return render(request, 'tables/mesas.html', context)


@login_required
def salvar_mesa(request, table_id=None):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    if request.method != 'POST':
        messages.error(request, 'Método inválido para salvar mesa.')
        return redirect('mesas')

    instance = None
    if table_id:
        instance = get_object_or_404(Table, pk=table_id, company=user_company)

    form = TableForm(request.POST, instance=instance, company=user_company)
    if form.is_valid():
        table = form.save(commit=False)
        table.company = user_company
        table.save()
        messages.success(request, 'Mesa salva com sucesso.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    redirect_target = request.POST.get('next') or reverse('mesas')
    return redirect(redirect_target)


@login_required
def excluir_mesa(request, table_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    table = get_object_or_404(Table, pk=table_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para excluir mesa.')
        return redirect('mesas')

    if table.orders.filter(status=TableOrder.Status.OPEN).exists():
        messages.error(
            request, 'Não é possível excluir uma mesa com comanda aberta.')
    elif table.orders.exists():
        orders_count = table.orders.count()
        messages.error(
            request,
            f'Não é possível excluir a mesa: existem {orders_count} comandas vinculadas. '
            'Remova ou arquive as comandas antes de excluir a mesa.',
        )
    else:
        try:
            table.delete()
            messages.success(request, 'Mesa removida com sucesso.')
        except ProtectedError:
            messages.error(
                request,
                'Não é possível excluir a mesa porque há registros vinculados. '
                'Remova as dependências antes de prosseguir.',
            )

    redirect_target = request.POST.get('next') or reverse('mesas')
    return redirect(redirect_target)


@login_required
def mesa_detalhe(request, table_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    table = (
        Table.objects.filter(company=user_company)
        .select_related('waiter')
        .prefetch_related(
            Prefetch(
                'orders',
                queryset=TableOrder.objects.filter(company=user_company)
                .prefetch_related(
                    'items__product',
                    Prefetch(
                        'sales',
                        queryset=Sales.objects.filter(
                            company=user_company).order_by('-date_added'),
                    ),
                )
                .order_by('-opened_at'),
            )
        )
        .filter(pk=table_id)
        .first()
    )
    if not table:
        messages.error(
            request, 'Mesa não encontrada ou já removida. Atualize a lista de mesas.')
        return redirect('mesas')

    cash_session_open = bool(get_open_cash_session(user_company))

    open_order = next((order for order in table.orders.all()
                      if order.status == TableOrder.Status.OPEN), None)
    closed_orders = []
    for order in table.orders.all():
        if order.status == TableOrder.Status.OPEN:
            continue

        if hasattr(order, 'sales'):
            order.latest_sale = next(iter(order.sales.all()), None)
        else:
            order.latest_sale = order.sales.order_by('-date_added').first()

        closed_orders.append(order)

    closed_orders = closed_orders[:10]

    if open_order:
        order_form = TableOrderForm(instance=open_order, company=user_company)
    else:
        order_form = TableOrderForm(
            initial={'people_count': table.capacity}, company=user_company)

    context = {
        'page_title': f'Mesa {table.number}',
        'table': table,
        'open_order': open_order,
        'order_form': order_form,
        'close_form': TableOrderCloseForm(instance=open_order) if open_order else TableOrderCloseForm(),
        'item_form': TableOrderItemForm(company=user_company),
        'table_form': TableForm(instance=table, company=user_company),
        'closed_orders': closed_orders,
        'has_waiters': Garcom.objects.filter(company=user_company, is_active=True).exists(),
        'cash_session_open': cash_session_open,
        'can_open_new_order': cash_session_open,
    }
    return render(request, 'tables/mesa_detail.html', context)


@login_required
def abrir_comanda(request, table_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    table = get_object_or_404(Table, pk=table_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para abrir comanda.')
        return redirect('mesa-detalhe', table_id=table.id)

    if not get_open_cash_session(user_company):
        messages.error(request, 'Abra o caixa para iniciar uma nova comanda.')
        return redirect('mesa-detalhe', table_id=table.id)

    if table.orders.filter(status=TableOrder.Status.OPEN).exists():
        messages.warning(
            request, 'Já existe uma comanda aberta para esta mesa.')
        return redirect('mesa-detalhe', table_id=table.id)

    if not Garcom.objects.filter(company=user_company, is_active=True).exists():
        messages.error(
            request, 'Cadastre um garçom ativo antes de abrir uma comanda.')
        return redirect('mesa-detalhe', table_id=table.id)

    form = TableOrderForm(request.POST, company=user_company)
    if form.is_valid():
        with transaction.atomic():
            order = form.save(commit=False)
            order.table = table
            order.company = user_company
            order.status = TableOrder.Status.OPEN
            order.opened_at = timezone.now()
            order.payment_method = ''
            order.save()
            order.recalculate_totals()

            table.waiter = order.waiter
            table.save(update_fields=['waiter'])
        messages.success(request, 'Comanda aberta com sucesso.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('mesa-detalhe', table_id=table.id)


@login_required
def atualizar_comanda(request, order_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    order = get_object_or_404(TableOrder, pk=order_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para atualizar comanda.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    form = TableOrderForm(request.POST, instance=order, company=user_company)
    if form.is_valid():
        with transaction.atomic():
            form.save()
            order.recalculate_totals()
            if order.status == TableOrder.Status.OPEN:
                order.table.waiter = order.waiter
                order.table.save(update_fields=['waiter'])
        messages.success(request, 'Comanda atualizada com sucesso.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def fechar_comanda(request, order_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    order = get_object_or_404(TableOrder, pk=order_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para fechar comanda.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    form = TableOrderCloseForm(request.POST, instance=order)
    if form.is_valid():
        order = form.save(commit=False)
        order.recalculate_totals(commit=False)

        try:
            payment_entries = parse_payment_entries(
                request.POST.getlist('payment_method[]'),
                request.POST.getlist('payment_amount[]'),
            )
            allocations, tendered_total, change_total = allocate_payments(
                order.total, payment_entries
            )
            primary_method = get_primary_payment_method(allocations)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('mesa-detalhe', table_id=order.table_id)

        with transaction.atomic():
            order.status = TableOrder.Status.CLOSED
            order.closed_at = timezone.now()
            order.payment_method = primary_method
            order.save()
            order.recalculate_totals()
            sale = create_sale_from_table_order(
                order,
                user_company,
                allocations=allocations,
                tendered_total=tendered_total,
                change_total=change_total,
                primary_method=primary_method,
                user=request.user,
            )

            table = order.table
            table.waiter = None
            table.save(update_fields=['waiter'])

        auto_open_print = getattr(user_company, 'auto_open_print', True)
        auto_print_flag = '1' if auto_open_print else '0'
        receipt_url = reverse('receipt-modal') + f'?id={sale.id}&auto_print={auto_print_flag}'
        print_status = False
        print_message = 'Impressao automatica desativada para esta empresa.'
        if auto_open_print:
            try:
                print_status, print_message = trigger_auto_print(sale)
            except Exception as exc:  # noqa: BLE001
                print_status, print_message = False, f'Erro ao acionar impressao: {exc}'
        if print_status:
            messages.success(request, f'Recibo enviado para impressora padrao. {print_message}')
        else:
            messages.info(
                request,
                f'Impressao automatica nao executada: {print_message}. '
                f'Use o recibo manual em {receipt_url} se necessario.',
            )

        messages.success(
            request,
            f'Comanda fechada com sucesso. Venda #{sale.code} registrada como Mesa {order.table.number}.',
        )
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def reabrir_comanda(request, order_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    order = get_object_or_404(TableOrder, pk=order_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para reabrir comanda.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    status, feedback = reopen_table_order(order, user_company)
    if status == 'success':
        messages.success(request, feedback)
    elif status == 'info':
        messages.info(request, feedback)
    else:
        messages.error(request, feedback)

    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def reabrir_venda_mesa(request, sale_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request, redirect_name='sales-page')
    if guard is not True:
        return guard

    sale = get_object_or_404(
        Sales.objects.select_related('table_order__table'),
        pk=sale_id,
        company=user_company,
    )

    sale_type = (sale.type or '').lower()
    if not sale_type.startswith('mesa'):
        messages.error(
            request, 'Apenas vendas originadas de mesas podem ser reabertas.')
        return redirect('sales-page')

    if request.method != 'POST':
        messages.error(
            request, 'Método inválido para reabrir comanda da venda.')
        return redirect('sales-page')

    order = sale.table_order
    if not order:
        messages.error(
            request, 'Esta venda não possui comanda vinculada para reabertura.')
        return redirect('sales-page')

    status, feedback = reopen_table_order(order, user_company)
    if status == 'success':
        messages.success(
            request, f'{feedback} A venda #{sale.code} foi revertida.')
    elif status == 'info':
        messages.info(request, feedback)
    else:
        messages.error(request, feedback)

    redirect_target = request.POST.get('next')
    if redirect_target:
        return redirect(redirect_target)
    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def excluir_comanda(request, order_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    order = TableOrder.objects.select_related(
        'table').filter(pk=order_id).first()
    if not order or order.company_id != getattr(user_company, 'id', None):
        messages.error(request, 'Comanda não encontrada para a empresa atual.')
        return redirect('mesas')

    if request.method != 'POST':
        messages.error(request, 'Método inválido para excluir comanda.')
        if order.table_id:
            return redirect('mesa-detalhe', table_id=order.table_id)
        return redirect('mesas')

    table = order.table if order.table_id else None

    with transaction.atomic():
        order_status = order.status
        order.delete()

        if table and order_status == TableOrder.Status.OPEN:
            if not table.orders.filter(status=TableOrder.Status.OPEN).exists():
                table.waiter = None
                table.save(update_fields=['waiter'])

    messages.success(request, 'Comanda removida com sucesso.')
    if table:
        return redirect('mesa-detalhe', table_id=table.id)
    return redirect('mesas')


@login_required
def adicionar_item_comanda(request, order_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    order = get_object_or_404(TableOrder, pk=order_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para adicionar item.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    if order.status != TableOrder.Status.OPEN:
        messages.error(
            request, 'Não é possível alterar itens de uma comanda fechada.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    form = TableOrderItemForm(request.POST, company=user_company)
    if form.is_valid():
        item = form.save(commit=False)
        product = item.product
        if product.status != 1:
            messages.error(request, 'Este item está indisponível no momento.')
        else:
            item.order = order
            item.unit_price = Decimal(str(product.price))
            item.save()
            messages.success(request, 'Item adicionado à comanda.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def atualizar_item_comanda(request, item_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    item = get_object_or_404(
        TableOrderItem.objects.select_related(
            'order', 'order__table', 'product'),
        pk=item_id,
        order__company=user_company,
    )
    order = item.order

    if request.method != 'POST':
        messages.error(request, 'Método inválido para atualizar item.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    if order.status != TableOrder.Status.OPEN:
        messages.error(
            request, 'Não é possível alterar itens de uma comanda fechada.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    form = TableOrderItemForm(
        request.POST, instance=item, company=user_company)
    if form.is_valid():
        item = form.save(commit=False)
        product = item.product
        if product.status != 1:
            messages.error(request, 'Este item está indisponível no momento.')
        else:
            item.order = order
            item.unit_price = Decimal(str(product.price))
            item.save()
            messages.success(request, 'Item atualizado.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def remover_item_comanda(request, item_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    item = get_object_or_404(
        TableOrderItem.objects.select_related('order', 'order__table'),
        pk=item_id,
        order__company=user_company,
    )
    order = item.order

    if request.method != 'POST':
        messages.error(request, 'Método inválido para remover item.')
        return redirect('mesa-detalhe', table_id=order.table_id)

    if order.status != TableOrder.Status.OPEN:
        messages.error(
            request, 'Não é possível alterar itens de uma comanda fechada.')
    else:
        item.delete()
        messages.success(request, 'Item removido da comanda.')

    return redirect('mesa-detalhe', table_id=order.table_id)


@login_required
def toggle_product_availability(request, product_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    product = get_object_or_404(Products, pk=product_id, company=user_company)

    if request.method != 'POST':
        messages.error(
            request, 'Método inválido para atualizar disponibilidade.')
        return redirect('mesas')

    product.status = 0 if product.status == 1 else 1
    product.save(update_fields=['status'])

    state = 'indisponível' if product.status == 0 else 'disponível'
    messages.success(request, f'Produto "{product.name}" agora está {state}.')

    redirect_target = request.POST.get('next') or request.META.get(
        'HTTP_REFERER') or reverse('mesas')
    return redirect(redirect_target)
