from django import forms

from p_v_App.models_tenant import Company


class ConfiguracaoSistemaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        printer_choices = kwargs.pop('printer_choices', [])
        super().__init__(*args, **kwargs)
        self.fields['default_printer'].widget.attrs['list'] = 'printers'
        if printer_choices:
            self.fields['default_printer'].widget.attrs['placeholder'] = 'Selecione ou digite outra impressora'

    class Meta:
        model = Company
        fields = ['default_printer', 'auto_open_print']
        widgets = {
            'default_printer': forms.TextInput(
                attrs={
                    'class': 'form-control ds-input',
                    'placeholder': 'Ex.: EPSON_TM-T20, PDF, Microsoft Print to PDF',
                }
            ),
            'auto_open_print': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input',
                }
            ),
        }
        labels = {
            'default_printer': 'Impressora padrão',
            'auto_open_print': 'Abrir tela de impressão automaticamente',
        }
        help_texts = {
            'default_printer': 'Será usada como destino padrão para impressões automáticas.',
            'auto_open_print': 'Quando ativo, abrirá a tela de impressão ao finalizar vendas/pedidos.',
        }
