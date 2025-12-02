from django import forms

from p_v_App.models import Garcom


class GarcomForm(forms.ModelForm):
    class Meta:
        model = Garcom
        fields = ['name', 'code', 'is_active']
        labels = {
            'name': 'Nome',
            'code': 'Código/Matrícula',
            'is_active': 'Ativo',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code:
            raise forms.ValidationError(
                'Informe o código ou matrícula do garçom.')
        if self.company:
            qs = Garcom.objects.filter(company=self.company, code__iexact=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    'Já existe um garçom com esse código nesta empresa.')
        return code
