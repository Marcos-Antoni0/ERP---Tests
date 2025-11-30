from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Company(models.Model):
    """
    Modelo que representa uma empresa (tenant)
    """
    name = models.CharField('Nome da Empresa', max_length=200)
    cnpj = models.CharField('CNPJ', max_length=18,
                            unique=True, null=True, blank=True)
    email = models.EmailField('Email', null=True, blank=True)
    phone = models.CharField('Telefone', max_length=20, null=True, blank=True)
    address = models.TextField('Endereço', null=True, blank=True)
    is_active = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField('Criado em', default=timezone.now)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    # Configurações específicas da empresa
    tax_rate = models.FloatField('Taxa de Imposto (%)', default=0.0)
    delivery_fee = models.FloatField('Taxa de Entrega Padrão', default=0.0)
    default_printer = models.CharField(
        'Impressora padrão',
        max_length=120,
        blank=True,
        help_text='Nome ou caminho da impressora padrão deste tenant.',
    )
    auto_open_print = models.BooleanField(
        'Abrir tela de impressão após finalizar',
        default=True,
        help_text='Quando marcado, a tela de impressão abre automaticamente após concluir uma venda ou pedido.',
    )

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """
    Extensão do modelo User para incluir informações de tenant
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile')
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='users')
    is_company_admin = models.BooleanField(
        'Administrador da Empresa', default=False)
    created_at = models.DateTimeField('Criado em', default=timezone.now)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Perfil de Usuário'
        verbose_name_plural = 'Perfis de Usuários'
        unique_together = ['user', 'company']

    def __str__(self):
        return f'{self.user.username} - {self.company.name}'


class TenantMixin(models.Model):
    """
    Mixin para adicionar funcionalidade de tenant aos modelos existentes
    """
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='%(class)s_set')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Garante que o company seja definido se não estiver
        if not self.company_id and hasattr(self, '_current_company'):
            self.company = self._current_company
        super().save(*args, **kwargs)


class TenantManager(models.Manager):
    """
    Manager personalizado para filtrar automaticamente por tenant
    """

    def __init__(self, *args, **kwargs):
        self._company = None
        super().__init__(*args, **kwargs)

    def set_company(self, company):
        """Define a empresa para filtrar os dados"""
        self._company = company
        return self

    def get_queryset(self):
        """Retorna queryset filtrado por empresa se definida"""
        qs = super().get_queryset()
        if self._company:
            qs = qs.filter(company=self._company)
        return qs

    def for_company(self, company):
        """Retorna queryset filtrado para uma empresa específica"""
        return self.get_queryset().filter(company=company)


def get_current_company(request):
    """
    Função utilitária para obter a empresa atual do usuário logado
    """
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        return request.user.profile.company
    return None


def set_current_company(obj, company):
    """
    Função utilitária para definir a empresa atual em um objeto
    """
    obj._current_company = company
    return obj
