from decimal import Decimal

from django import forms

from p_v_App.models import Garcom, Products, Table, TableOrder, TableOrderItem


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ['number', 'name', 'capacity', 'is_active', 'notes']
        labels = {
            'number': 'Número',
            'name': 'Identificação',
            'capacity': 'Lugares',
            'is_active': 'Ativa',
            'notes': 'Observações',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_number(self):
        number = self.cleaned_data.get('number')
        if number and number <= 0:
            raise forms.ValidationError(
                'O número da mesa deve ser maior que zero.')
        return number

    def clean(self):
        cleaned = super().clean()
        if self.company:
            qs = Table.objects.filter(
                company=self.company, number=cleaned.get('number'))
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    'Já existe uma mesa com esse número nesta empresa.')
        return cleaned


class TableOrderForm(forms.ModelForm):
    service_charge = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        min_value=0,
        label='Taxa de serviço (%)',
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0',
                   'step': '0.1', 'placeholder': 'Ex.: 10 para 10%'}
        ),
        help_text='Informe a taxa em porcentagem. Ex.: 10 aplica 10% sobre o subtotal.',
    )
    discount_amount = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        min_value=0,
        label='Desconto',
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
    )
    discount_reason = forms.CharField(
        required=False,
        label='Motivo do desconto',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Descreva o motivo do desconto',
                'maxlength': 255,
            }
        ),
    )

    class Meta:
        model = TableOrder
        fields = ['waiter', 'people_count', 'service_charge',
                  'discount_amount', 'discount_reason', 'notes']
        labels = {
            'waiter': 'Garçom',
            'people_count': 'Quantidade de pessoas',
            'notes': 'Observações',
        }
        widgets = {
            'waiter': forms.Select(attrs={'class': 'form-select'}),
            'people_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if self.company is not None:
            qs = Garcom.objects.filter(company=self.company, is_active=True)
            if self.instance and self.instance.pk and self.instance.waiter_id:
                qs = qs | Garcom.objects.filter(pk=self.instance.waiter_id)
            self.fields['waiter'].queryset = qs.order_by('name')
        self.fields['waiter'].required = True

    def clean_service_charge(self):
        value = self.cleaned_data.get('service_charge')
        return value if value is not None else Decimal('0')

    def clean(self):
        cleaned = super().clean()
        discount = cleaned.get('discount_amount') or Decimal('0')
        reason = (cleaned.get('discount_reason') or '').strip()
        if len(reason) > 255:
            reason = reason[:255]
        if discount > 0 and not reason:
            self.add_error('discount_reason',
                           'Informe o motivo do desconto aplicado.')
        elif discount <= 0:
            reason = ''
        cleaned['discount_reason'] = reason
        return cleaned

    def clean_discount_amount(self):
        value = self.cleaned_data.get('discount_amount')
        return value if value is not None else Decimal('0')


class TableOrderCloseForm(forms.ModelForm):
    service_charge = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        min_value=0,
        label='Taxa de serviço (%)',
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0',
                   'step': '0.1', 'placeholder': 'Informe o percentual'}
        ),
        help_text='Percentual aplicado sobre o subtotal.',
    )
    discount_amount = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        min_value=0,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
    )
    discount_reason = forms.CharField(
        required=False,
        label='Motivo do desconto',
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Descreva o motivo do desconto',
                'maxlength': 255,
            }
        ),
    )

    class Meta:
        model = TableOrder
        fields = ['service_charge', 'discount_amount',
                  'discount_reason', 'notes']
        labels = {
            'service_charge': 'Taxa de serviço',
            'discount_amount': 'Desconto',
            'notes': 'Observações finais',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def clean_service_charge(self):
        value = self.cleaned_data.get('service_charge')
        return value if value is not None else Decimal('0')

    def clean(self):
        cleaned = super().clean()
        discount = cleaned.get('discount_amount') or Decimal('0')
        reason = (cleaned.get('discount_reason') or '').strip()
        if len(reason) > 255:
            reason = reason[:255]
        if discount > 0 and not reason:
            self.add_error('discount_reason',
                           'Informe o motivo do desconto aplicado.')
        elif discount <= 0:
            reason = ''
        cleaned['discount_reason'] = reason
        return cleaned

    def clean_discount_amount(self):
        value = self.cleaned_data.get('discount_amount')
        return value if value is not None else Decimal('0')


class TableOrderItemForm(forms.ModelForm):
    class Meta:
        model = TableOrderItem
        fields = ['product', 'quantity', 'notes']
        labels = {
            'product': 'Produto',
            'quantity': 'Quantidade',
            'notes': 'Observações',
        }
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.01', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        if company is not None:
            self.fields['product'].queryset = (
                Products.objects.filter(
                    company=company, status=1, is_combo=False)
                .order_by('name')
            )
        self.fields['quantity'].min_value = Decimal('0.01')

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None or qty <= 0:
            raise forms.ValidationError('Informe uma quantidade válida.')
        return qty
