from decimal import Decimal

from django import forms

from p_v_App.models import CashMovement, Sales


PAYMENT_METHOD_CHOICES = [
    choice for choice in Sales.FORMA_PAGAMENTO_CHOICES if choice[0] != 'MULTI'
]


class CashOpenForm(forms.Form):
    opening_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        label='Saldo inicial',
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
    )
    opening_note = forms.CharField(
        label='Observações',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )


class CashMovementForm(forms.Form):
    type = forms.ChoiceField(
        label='Tipo de movimentação',
        choices=CashMovement.Type.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    amount = forms.DecimalField(
        label='Valor',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
    )
    payment_method = forms.ChoiceField(
        label='Forma de pagamento',
        choices=CashMovement.MOVEMENT_PAYMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
    )
    description = forms.CharField(
        label='Descrição',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    note = forms.CharField(
        label='Observação',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def clean_payment_method(self):
        method = self.cleaned_data.get('payment_method') or ''
        method = method.strip()
        if not method:
            raise forms.ValidationError(
                'Informe a forma de pagamento utilizada.')
        if method == 'MULTI':
            raise forms.ValidationError(
                'Selecione uma forma de pagamento válida.')
        return method

    def clean(self):
        cleaned = super().clean()
        movement_type = cleaned.get('type')
        note = cleaned.get('note', '')
        if movement_type == CashMovement.Type.EXIT and not note.strip():
            raise forms.ValidationError('Informe o motivo da saída de caixa.')
        return cleaned


class CashCloseForm(forms.Form):
    closing_amount = forms.DecimalField(
        label='Saldo em caixa',
        max_digits=10,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
    )
    closing_note = forms.CharField(
        label='Observações do fechamento',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )
