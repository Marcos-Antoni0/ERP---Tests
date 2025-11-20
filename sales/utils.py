from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import textwrap
import unicodedata
from typing import Iterable, Sequence

from django.db import transaction
from django.db.models import Sum

from p_v_App.models import CashMovement, CashRegisterSession, SalePayment, Sales

CENTS = Decimal("0.01")
VALID_PAYMENT_METHODS = {
    code
    for code, _ in Sales.FORMA_PAGAMENTO_CHOICES
    if code != "MULTI"
}


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def quantize_currency(value: Decimal) -> Decimal:
    return _to_decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def parse_payment_entries(raw_methods: Sequence[str], raw_amounts: Sequence[str]) -> list[dict]:
    entries: list[dict] = []
    for method, amount in zip(raw_methods, raw_amounts):
        method = (method or "").strip().upper()
        if not method:
            continue
        if method not in VALID_PAYMENT_METHODS:
            raise ValueError("Forma de pagamento inválida informada.")
        amount_value = quantize_currency(amount)
        if amount_value <= Decimal("0"):
            continue
        entries.append({"method": method, "amount": amount_value})
    if not entries:
        raise ValueError("Informe ao menos um pagamento com valor positivo.")
    return entries


def allocate_payments(total_due: Decimal, entries: Sequence[dict]) -> tuple[list[dict], Decimal, Decimal]:
    if total_due is None:
        raise ValueError("Total da venda não informado.")
    due = quantize_currency(total_due)
    if due <= Decimal("0"):
        raise ValueError("O total da venda deve ser maior que zero.")

    remaining = due
    allocations: list[dict] = []
    tendered_total = Decimal("0")
    change_total = Decimal("0")

    for entry in entries:
        method = entry["method"]
        tendered = quantize_currency(entry["amount"])
        if tendered <= Decimal("0"):
            continue

        tendered_total += tendered
        applied = tendered
        change_piece = Decimal("0")

        if remaining <= Decimal("0"):
            if method != "DINHEIRO":
                raise ValueError(
                    "Após quitar o valor total, pagamentos adicionais só são permitidos em dinheiro."
                )
            applied = Decimal("0")
            change_piece = tendered
        elif tendered > remaining:
            if method != "DINHEIRO":
                raise ValueError(
                    "O valor informado para a forma de pagamento selecionada excede o saldo a pagar."
                )
            applied = remaining
            change_piece = tendered - remaining
        else:
            applied = tendered

        remaining -= applied
        change_total += change_piece

        allocations.append(
            {
                "method": method,
                "tendered": tendered,
                "applied": applied,
                "change": change_piece,
            }
        )

    if remaining > Decimal("0.009"):
        raise ValueError("Os pagamentos não cobrem o valor total da venda.")

    return allocations, tendered_total, change_total


def get_primary_payment_method(allocations: Iterable[dict]) -> str:
    allocations = list(allocations)
    methods = {allocation["method"] for allocation in allocations if allocation.get("applied") > 0}
    if not allocations:
        return "PIX"
    if len(methods) == 1:
        return next(iter(methods))
    return "MULTI"


def get_open_cash_session(company) -> CashRegisterSession | None:
    return (
        CashRegisterSession.objects.filter(company=company, status=CashRegisterSession.Status.OPEN)
        .order_by("-opened_at")
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
                method=allocation["method"],
                tendered_amount=allocation["tendered"],
                applied_amount=allocation["applied"],
                change_amount=allocation["change"],
                recorded_by=user,
            )
            if not session:
                continue

            if payment.tendered_amount > Decimal("0"):
                CashMovement.objects.create(
                    company=company,
                    session=session,
                    type=CashMovement.Type.ENTRY,
                    amount=payment.tendered_amount,
                    payment_method=payment.method,
                    description=f"Pagamento {sale.code}",
                    sale=sale,
                    recorded_by=user,
                )

            if payment.change_amount > Decimal("0"):
                CashMovement.objects.create(
                    company=company,
                    session=session,
                    type=CashMovement.Type.EXIT,
                    amount=payment.change_amount,
                    payment_method="DINHEIRO",
                    description=f"Troco {sale.code}",
                    sale=sale,
                    recorded_by=user,
                )


def payment_summary_for_sale(sale: Sales) -> list[dict]:
    summary = []
    for payment in sale.payments.all().order_by("-recorded_at"):
        summary.append(
            {
                "method": payment.get_method_display(),
                "method_code": payment.method,
                "tendered": payment.tendered_amount,
                "applied": payment.applied_amount,
                "change": payment.change_amount,
                "recorded_at": payment.recorded_at,
                "recorded_by": payment.recorded_by,
            }
        )
    return summary


def _format_currency(value: Decimal) -> str:
    return f"R$ {quantize_currency(value):.2f}".replace(".", ",", 1)


def _sanitize_pdf_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf_from_lines(lines: list[str]) -> bytes:
    page_width = 595
    page_height = 842
    margin_left = 40
    top = page_height - 40
    leading = 14

    text_commands = ["BT", "/F1 11 Tf", f"{margin_left} {top} Td", f"{leading} TL"]
    for raw_line in lines:
        if not raw_line:
            text_commands.append("T*")
            continue
        wrapped_lines = textwrap.wrap(
            raw_line,
            width=90,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=False,
        ) or [""]
        for wrapped in wrapped_lines:
            sanitized = _sanitize_pdf_text(wrapped)
            text_commands.append(f"({sanitized}) Tj")
            text_commands.append("T*")
    text_commands.append("ET")
    content_stream = "\n".join(text_commands)
    content_bytes = content_stream.encode("latin-1")

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    objects = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>"
    )
    objects.append(f"<< /Length {len(content_bytes)} >>\nstream\n{content_stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{index} 0 obj\n".encode("ascii"))
        buffer.write(obj.encode("latin-1"))
        buffer.write(b"\nendobj\n")

    xref_position = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buffer.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    buffer.write(b"trailer\n")
    buffer.write(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    buffer.write(f"startxref\n{xref_position}\n%%EOF".encode("ascii"))
    return buffer.getvalue()


def generate_cash_report_pdf(session: CashRegisterSession) -> bytes:
    lines: list[str] = []

    def add_line(text: str = "") -> None:
        lines.append(text)

    add_line(f"Relatorio de Caixa - {session.company.name}")
    closed_label = session.closed_at.strftime("%d/%m/%Y %H:%M") if session.closed_at else "-"
    add_line(f"Periodo: {session.opened_at:%d/%m/%Y %H:%M} - {closed_label}")
    add_line(
        "Operador abertura: "
        f"{session.opened_by.get_full_name() or session.opened_by.username}"
    )
    if session.closed_by:
        add_line(
            "Operador fechamento: "
            f"{session.closed_by.get_full_name() or session.closed_by.username}"
        )

    add_line()
    add_line("Resumo financeiro")
    add_line(f"Saldo inicial: {_format_currency(session.opening_amount)}")
    add_line(f"Entradas registradas: {_format_currency(session.total_entries())}")
    add_line(f"Saidas registradas: {_format_currency(session.total_exits())}")
    add_line(f"Saldo esperado: {_format_currency(session.expected_balance())}")
    add_line(
        f"Saldo informado no fechamento: {_format_currency(session.closing_amount)}"
    )
    difference = quantize_currency(session.closing_amount) - session.expected_balance()
    add_line(f"Diferenca apurada: {_format_currency(difference)}")

    sale_ids = list(
        session.movements.filter(sale__isnull=False).values_list("sale_id", flat=True).distinct()
    )
    if sale_ids:
        add_line()
        add_line("Pagamentos por forma")
        payment_totals = (
            SalePayment.objects.filter(sale_id__in=sale_ids)
            .values("method")
            .annotate(
                total_applied=Sum("applied_amount"),
                total_tendered=Sum("tendered_amount"),
                total_change=Sum("change_amount"),
            )
            .order_by("method")
        )
        for item in payment_totals:
            method_label = dict(Sales.FORMA_PAGAMENTO_CHOICES).get(item["method"], item["method"])
            add_line(
                f"- {method_label}: {_format_currency(item['total_applied'])}"
                f" (Recebido: {_format_currency(item['total_tendered'])}; Troco: {_format_currency(item['total_change'])})"
            )

        discount_entries = (
            Sales.objects.filter(id__in=sale_ids, discount_total__gt=0)
            .values("code", "discount_total", "discount_reason", "grand_total")
            .order_by("code")
        )
        if discount_entries:
            add_line()
            add_line("Descontos concedidos")
            total_discount = Decimal("0")
            for entry in discount_entries:
                discount_amount = quantize_currency(entry["discount_total"])
                total_discount += discount_amount
                reason = entry.get("discount_reason") or "Não informado"
                final_total = quantize_currency(entry.get("grand_total") or Decimal("0"))
                add_line(
                    f"- {entry['code']}: {_format_currency(discount_amount)} | Motivo: {reason}"
                )
                add_line(
                    f"  Valor final da venda: {_format_currency(final_total)}"
                )
            add_line(f"Total de descontos: {_format_currency(total_discount)}")

    manual_movements = session.movements.filter(sale__isnull=True).order_by("recorded_at")
    if manual_movements.exists():
        add_line()
        add_line("Movimentacoes manuais")
        for movement in manual_movements:
            header = (
                f"[{movement.recorded_at:%d/%m %H:%M}] {movement.get_type_display()} - "
                f"{_format_currency(movement.amount)} via "
                f"{movement.get_payment_method_display() if movement.payment_method else 'N/I'}"
            )
            add_line(header)
            add_line(f"  Descricao: {movement.description}")
            if movement.note:
                add_line(f"  Observacao: {movement.note}")

    if session.closing_note:
        add_line()
        add_line("Observacoes do fechamento")
        add_line(session.closing_note)

    return _render_pdf_from_lines(lines)
