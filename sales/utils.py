from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import textwrap
import unicodedata
from typing import Iterable, Sequence

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from p_v_App.models import (
    CashMovement,
    CashRegisterSession,
    Pedido,
    PedidoItem,
    SalePayment,
    Sales,
    salesItems,
)
from debts.models import Debt

CENTS = Decimal('0.01')
VALID_PAYMENT_METHODS = {
    code
    for code, _ in Sales.FORMA_PAGAMENTO_CHOICES
    if code != 'MULTI'
}


def _safe_get_default_printer(company) -> str:
    return (getattr(company, 'default_printer', '') or '').strip()


def print_sale_receipt_to_printer(sale: Sales, *, printer_name: str | None = None) -> tuple[bool, str]:
    """
    Tenta imprimir um recibo simplificado na impressora informada.
    Depende de win32print (Windows). Em outros ambientes, retorna mensagem de fallback.
    """
    printer_name = printer_name or _safe_get_default_printer(getattr(sale, 'company', None))
    if not printer_name:
        return False, 'Nenhuma impressora padrao configurada.'

    items = [
        {
            'name': getattr(item.product_id, 'name', 'Item'),
            'qty': item.qty,
            'price': item.price,
        }
        for item in salesItems.objects.filter(sale_id=sale).select_related('product_id')
    ]

    payments = [
        {
            'label': payment.get_method_display(),
            'applied': payment.applied_amount,
            'tendered': payment.tendered_amount,
            'change': payment.change_amount,
        }
        for payment in sale.payments.all().order_by('recorded_at')
    ]

    table_number = None
    try:
        table_number = getattr(getattr(sale, 'table', None), 'number', None)
    except Exception:
        table_number = None

    payload = _build_receipt_payload(
        header_label='Venda',
        code=sale.code,
        company_name=getattr(sale.company, 'name', 'Empresa'),
        company_cnpj=getattr(sale.company, 'cnpj', ''),
        created_at=sale.date_added,
        table_number=table_number,
        items=items,
        delivery_fee=sale.delivery_fee or 0,
        discount_total=sale.discount_total or 0,
        grand_total=sale.grand_total or 0,
        payments=payments,
    )

    return _send_payload_to_printer(printer_name, payload)


def print_pedido_receipt_to_printer(pedido: Pedido, *, printer_name: str | None = None) -> tuple[bool, str]:
    printer_name = printer_name or _safe_get_default_printer(getattr(pedido, 'company', None))
    if not printer_name:
        return False, 'Nenhuma impressora padrao configurada.'

    items = [
        {
            'name': getattr(item.product, 'name', 'Item'),
            'qty': item.qty,
            'price': item.price,
        }
        for item in PedidoItem.objects.filter(pedido=pedido).select_related('product')
    ]

    payments = []
    if pedido.tendered_amount:
        payments.append(
            {
                'label': dict(Sales.FORMA_PAGAMENTO_CHOICES).get(
                    pedido.forma_pagamento, pedido.forma_pagamento
                ),
                'applied': pedido.grand_total,
                'tendered': pedido.tendered_amount,
                'change': pedido.amount_change,
            }
        )

    payload = _build_receipt_payload(
        header_label='Pedido',
        code=pedido.code,
        company_name=getattr(pedido.company, 'name', 'Empresa'),
        company_cnpj=getattr(pedido.company, 'cnpj', ''),
        created_at=pedido.date_added,
        items=items,
        delivery_fee=getattr(pedido, 'taxa_entrega', 0) or 0,
        discount_total=pedido.discount_total or 0,
        grand_total=pedido.grand_total or 0,
        payments=payments,
    )

    return _send_payload_to_printer(printer_name, payload)


def _build_receipt_payload(
    *,
    header_label: str,
    code: str,
    company_name: str,
    company_cnpj: str | None,
    created_at,
    table_number=None,
    items: list[dict],
    delivery_fee,
    discount_total,
    grand_total,
    payments: list[dict] | None = None,
) -> str:
    lines: list[str] = []
    lines.append(company_name or 'Empresa')
    cnpj = (company_cnpj or '').strip()
    if cnpj:
        lines.append(f'CNPJ: {cnpj}')
    lines.append(f'{header_label}: {code}')
    if created_at:
        try:
            display_dt = timezone.localtime(created_at)
        except Exception:
            display_dt = created_at
        lines.append(f'Data: {display_dt:%d/%m/%Y %H:%M}')
    if table_number:
        lines.append(f'Mesa: {table_number}')
    lines.append('-' * 32)

    total_itens = Decimal('0')
    for item in items:
        name = (item.get('name') or 'Item')[:20]
        qty = _to_decimal(item.get('qty'))
        price = _to_decimal(item.get('price'))
        line_total = qty * price
        total_itens += line_total
        lines.append(f'{name:<20}')
        lines.append(f'{qty:>5} x {price:>8.2f} = {line_total:>8.2f}')

    lines.append('-' * 32)
    delivery = _to_decimal(delivery_fee)
    discount = _to_decimal(discount_total)
    if delivery > 0:
        lines.append(f'Taxa entrega: R$ {delivery:.2f}')
    if discount > 0:
        lines.append(f'Desconto:    -R$ {discount:.2f}')
    lines.append(f'Subtotal:    R$ {total_itens:.2f}')
    lines.append(f'Total:       R$ {_to_decimal(grand_total):.2f}')

    payments = payments or []
    if payments:
        lines.append('-' * 32)
        lines.append('Pagamentos:')
        total_tendered = Decimal('0')
        total_change = Decimal('0')
        for payment in payments:
            label = payment.get('label') or 'Pagamento'
            applied = _to_decimal(payment.get('applied'))
            tendered = _to_decimal(payment.get('tendered'))
            change = _to_decimal(payment.get('change'))
            lines.append(f'{label:<12} R$ {applied:.2f}')
            total_tendered += tendered
            total_change += change
        if total_tendered > 0:
            lines.append(f'Recebido:    R$ {total_tendered:.2f}')
        if total_change > 0:
            lines.append(f'Troco:       R$ {total_change:.2f}')

    lines.append('-' * 32)
    lines.append('Obrigado pela preferencia!')
    lines.append('')  # linha final simples para corte
    return '\n'.join(lines)


def _send_payload_to_printer(printer_name: str, payload: str) -> tuple[bool, str]:
    try:
        import win32print
    except Exception:
        return False, 'Modulo win32print indisponivel neste ambiente.'

    try:
        handle = win32print.OpenPrinter(printer_name)
    except Exception as exc:
        return False, f'Nao foi possivel abrir a impressora "{printer_name}": {exc}'

    try:
        win32print.StartDocPrinter(handle, 1, ('ERP FortTech - Recibo', None, 'RAW'))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, payload.encode(settings.DEFAULT_CHARSET))
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
    except Exception as exc:
        return False, f'Erro ao enviar impressao: {exc}'
    finally:
        try:
            win32print.ClosePrinter(handle)
        except Exception:
            pass

    return True, f'Recibo enviado para {printer_name}'


def trigger_auto_print(record) -> tuple[bool, str]:
    try:
        if isinstance(record, Sales):
            return print_sale_receipt_to_printer(record)
        if isinstance(record, Pedido):
            return print_pedido_receipt_to_printer(record)
    except Exception as exc:
        return False, f'Erro ao processar impressao automatica: {exc}'
    return False, 'Tipo de registro nao suportado para impressao automatica.'


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def quantize_currency(value: Decimal) -> Decimal:
    return _to_decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def parse_payment_entries(raw_methods: Sequence[str], raw_amounts: Sequence[str], *, allow_empty: bool = False) -> list[dict]:
    entries: list[dict] = []
    for method, amount in zip(raw_methods, raw_amounts):
        method = (method or '').strip().upper()
        if not method:
            continue
        if method not in VALID_PAYMENT_METHODS:
            raise ValueError('Forma de pagamento inválida informada.')
        amount_value = quantize_currency(amount)
        if amount_value <= Decimal('0'):
            continue
        entries.append({'method': method, 'amount': amount_value})
    if not entries and not allow_empty:
        raise ValueError('Informe ao menos um pagamento com valor positivo.')
    return entries


def allocate_payments(total_due: Decimal, entries: Sequence[dict], *, allow_partial: bool = False) -> tuple[list[dict], Decimal, Decimal]:
    if total_due is None:
        raise ValueError('Total da venda não informado.')
    due = quantize_currency(total_due)
    if due <= Decimal('0'):
        raise ValueError('O total da venda deve ser maior que zero.')

    remaining = due
    allocations: list[dict] = []
    tendered_total = Decimal('0')
    change_total = Decimal('0')

    for entry in entries:
        method = entry['method']
        tendered = quantize_currency(entry['amount'])
        if tendered <= Decimal('0'):
            continue

        tendered_total += tendered
        applied = tendered
        change_piece = Decimal('0')

        if remaining <= Decimal('0'):
            if method != 'DINHEIRO':
                raise ValueError(
                    'Após quitar o valor total, pagamentos adicionais só são permitidos em dinheiro.'
                )
            applied = Decimal('0')
            change_piece = tendered
        elif tendered > remaining:
            if method != 'DINHEIRO':
                raise ValueError(
                    'O valor informado para a forma de pagamento selecionada excede o saldo a pagar.'
                )
            applied = remaining
            change_piece = tendered - remaining
        else:
            applied = tendered

        remaining -= applied
        change_total += change_piece

        allocations.append(
            {
                'method': method,
                'tendered': tendered,
                'applied': applied,
                'change': change_piece,
            }
        )

    if remaining > Decimal('0.009') and not allow_partial:
        raise ValueError('Os pagamentos nao cobrem o valor total da venda.')

    return allocations, tendered_total, change_total


def get_primary_payment_method(allocations: Iterable[dict]) -> str:
    allocations = list(allocations)
    methods = {allocation['method']
               for allocation in allocations if allocation.get('applied') > 0}
    if not allocations:
        return 'PIX'
    if len(methods) == 1:
        return next(iter(methods))
    return 'MULTI'


def get_open_cash_session(company) -> CashRegisterSession | None:
    return (
        CashRegisterSession.objects.filter(
            company=company, status=CashRegisterSession.Status.OPEN)
        .order_by('-opened_at')
        .first()
    )


def register_sale_payments(sale: Sales, allocations: Sequence[dict], user) -> None:
    company = sale.company
    session = get_open_cash_session(company)

    with transaction.atomic():
        for allocation in allocations:
            payment = SalePayment.objects.create(
                company=company,
                sale=sale,
                method=allocation['method'],
                tendered_amount=allocation['tendered'],
                applied_amount=allocation['applied'],
                change_amount=allocation['change'],
                recorded_by=user,
            )
            if not session:
                continue

            if payment.tendered_amount > Decimal('0'):
                CashMovement.objects.create(
                    company=company,
                    session=session,
                    type=CashMovement.Type.ENTRY,
                    amount=payment.tendered_amount,
                    payment_method=payment.method,
                    description=f'Pagamento {sale.code}',
                    sale=sale,
                    recorded_by=user,
                )

            if payment.change_amount > Decimal('0'):
                CashMovement.objects.create(
                    company=company,
                    session=session,
                    type=CashMovement.Type.EXIT,
                    amount=payment.change_amount,
                    payment_method='DINHEIRO',
                    description=f'Troco {sale.code}',
                    sale=sale,
                    recorded_by=user,
                )


def payment_summary_for_sale(sale: Sales) -> list[dict]:
    summary = []
    for payment in sale.payments.all().order_by('-recorded_at'):
        summary.append(
            {
                'method': payment.get_method_display(),
                'method_code': payment.method,
                'tendered': payment.tendered_amount,
                'applied': payment.applied_amount,
                'change': payment.change_amount,
                'recorded_at': payment.recorded_at,
                'recorded_by': payment.recorded_by,
            }
        )
    return summary


def _format_currency(value: Decimal) -> str:
    return f'R$ {quantize_currency(value):.2f}'.replace('.', ',', 1)


def _sanitize_pdf_text(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value or '')
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _render_pdf_from_lines(lines: list[str]) -> bytes:
    page_width = 595
    page_height = 842
    margin_left = 40
    top = page_height - 40
    leading = 14

    text_commands = ['BT', '/F1 11 Tf',
                     f'{margin_left} {top} Td', f'{leading} TL']
    for raw_line in lines:
        if not raw_line:
            text_commands.append('T*')
            continue
        wrapped_lines = textwrap.wrap(
            raw_line,
            width=90,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=False,
        ) or ['']
        for wrapped in wrapped_lines:
            sanitized = _sanitize_pdf_text(wrapped)
            text_commands.append(f'({sanitized}) Tj')
            text_commands.append('T*')
    text_commands.append('ET')
    content_stream = '\n'.join(text_commands)
    content_bytes = content_stream.encode('latin-1')

    buffer = BytesIO()
    buffer.write(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    objects = []
    objects.append('<< /Type /Catalog /Pages 2 0 R >>')
    objects.append('<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    objects.append(
        f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] /Contents 4 0 R '
        '/Resources << /Font << /F1 5 0 R >> >> >>'
    )
    objects.append(
        f'<< /Length {len(content_bytes)} >>\nstream\n{content_stream}\nendstream')
    objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')

    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f'{index} 0 obj\n'.encode('ascii'))
        buffer.write(obj.encode('latin-1'))
        buffer.write(b'\nendobj\n')

    xref_position = buffer.tell()
    buffer.write(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    buffer.write(b'0000000000 65535 f \n')
    for offset in offsets:
        buffer.write(f'{offset:010d} 00000 n \n'.encode('ascii'))
    buffer.write(b'trailer\n')
    buffer.write(
        f'<< /Size {len(objects) + 1} /Root 1 0 R >>\n'.encode('ascii'))
    buffer.write(f'startxref\n{xref_position}\n%%EOF'.encode('ascii'))
    return buffer.getvalue()


def generate_cash_report_pdf(session: CashRegisterSession) -> bytes:
    lines: list[str] = []

    def add_line(text: str = '') -> None:
        lines.append(text)

    add_line(f'Relatorio de Caixa - {session.company.name}')
    closed_label = session.closed_at.strftime(
        '%d/%m/%Y %H:%M') if session.closed_at else '-'
    add_line(f'Periodo: {session.opened_at:%d/%m/%Y %H:%M} - {closed_label}')
    add_line(
        'Operador abertura: '
        f'{session.opened_by.get_full_name() or session.opened_by.username}'
    )
    if session.closed_by:
        add_line(
            'Operador fechamento: '
            f'{session.closed_by.get_full_name() or session.closed_by.username}'
        )

    add_line()
    add_line('Resumo financeiro')
    add_line(f'Saldo inicial: {_format_currency(session.opening_amount)}')
    add_line(
        f'Entradas registradas: {_format_currency(session.total_entries())}')
    add_line(f'Saidas registradas: {_format_currency(session.total_exits())}')
    add_line(f'Saldo esperado: {_format_currency(session.expected_balance())}')
    add_line(
        f'Saldo informado no fechamento: {_format_currency(session.closing_amount)}'
    )
    difference = quantize_currency(
        session.closing_amount) - session.expected_balance()
    add_line(f'Diferenca apurada: {_format_currency(difference)}')

    period_start = session.opened_at
    period_end = session.closed_at or timezone.now()
    period_sales = Sales.objects.filter(
        company=session.company,
        date_added__gte=period_start,
        date_added__lte=period_end,
    )
    total_vendido = (
        period_sales.aggregate(total=Sum('grand_total')).get('total')
        or Decimal('0')
    )
    total_apurado = (
        SalePayment.objects.filter(sale_id__in=period_sales.values('id'))
        .aggregate(total=Sum('applied_amount'))
        .get('total')
        or Decimal('0')
    )
    prazo_debts = Debt.objects.filter(
        company=session.company,
        sale_id__in=period_sales.values('id'),
    ).select_related('client', 'sale')
    total_prazo = (
        prazo_debts.filter(status=Debt.Status.OPEN)
        .aggregate(total=Sum('amount'))
        .get('total')
        or Decimal('0')
    )

    add_line()
    add_line('Vendas a Prazo')
    add_line(f'Total vendido (incl. a prazo): {_format_currency(total_vendido)}')
    add_line(f'Total apurado (recebido): {_format_currency(total_apurado)}')
    add_line(f'Vendas a prazo (em debito): {_format_currency(total_prazo)}')

    if prazo_debts.exists():
        add_line('Detalhamento de vendas a prazo')
        for debt in prazo_debts.order_by('-created_at'):
            sale = getattr(debt, 'sale', None)
            sale_label = f"#{sale.code}" if sale else 'N/I'
            sale_date = sale.date_added.strftime(
                '%d/%m/%Y %H:%M') if sale else '-'
            client_name = debt.client.name if debt.client_id else 'Cliente não informado'
            status_label = dict(Debt.Status.choices).get(debt.status, debt.status)
            add_line(
                f"- {client_name} | {sale_label} | {sale_date} | Valor: {_format_currency(debt.amount)} | Status: {status_label}"
            )

    sale_ids = list(
        session.movements.filter(sale__isnull=False).values_list(
            'sale_id', flat=True).distinct()
    )
    if sale_ids:
        add_line()
        add_line('Pagamentos por forma')
        payment_totals = (
            SalePayment.objects.filter(sale_id__in=sale_ids)
            .values('method')
            .annotate(
                total_applied=Sum('applied_amount'),
                total_tendered=Sum('tendered_amount'),
                total_change=Sum('change_amount'),
            )
            .order_by('method')
        )
        for item in payment_totals:
            method_label = dict(Sales.FORMA_PAGAMENTO_CHOICES).get(
                item['method'], item['method'])
            add_line(
                f"- {method_label}: {_format_currency(item['total_applied'])}"
                f" (Recebido: {_format_currency(item['total_tendered'])}; Troco: {_format_currency(item['total_change'])})"
            )

        discount_entries = (
            Sales.objects.filter(id__in=sale_ids, discount_total__gt=0)
            .values('code', 'discount_total', 'discount_reason', 'grand_total')
            .order_by('code')
        )
        if discount_entries:
            add_line()
            add_line('Descontos concedidos')
            total_discount = Decimal('0')
            for entry in discount_entries:
                discount_amount = quantize_currency(entry['discount_total'])
                total_discount += discount_amount
                reason = entry.get('discount_reason') or 'Não informado'
                final_total = quantize_currency(
                    entry.get('grand_total') or Decimal('0'))
                add_line(
                    f"- {entry['code']}: {_format_currency(discount_amount)} | Motivo: {reason}"
                )
                add_line(
                    f'  Valor final da venda: {_format_currency(final_total)}'
                )
            add_line(f'Total de descontos: {_format_currency(total_discount)}')

    manual_movements = session.movements.filter(
        sale__isnull=True).order_by('recorded_at')
    if manual_movements.exists():
        add_line()
        add_line('Movimentacoes manuais')
        for movement in manual_movements:
            header = (
                f"[{movement.recorded_at:%d/%m %H:%M}] {movement.get_type_display()} - "
                f"{_format_currency(movement.amount)} via "
                f"{movement.get_payment_method_display() if movement.payment_method else 'N/I'}"
            )
            add_line(header)
            add_line(f'  Descricao: {movement.description}')
            if movement.note:
                add_line(f'  Observacao: {movement.note}')

    if session.closing_note:
        add_line()
        add_line('Observacoes do fechamento')
        add_line(session.closing_note)

    return _render_pdf_from_lines(lines)
