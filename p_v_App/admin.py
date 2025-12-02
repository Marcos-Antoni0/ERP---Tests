from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models_tenant import Company, UserProfile
from .models import (
    Category,
    Products,
    ProductComboItem,
    Sales,
    salesItems,
    Pedido,
    Estoque,
    Garcom,
    Table,
    TableOrder,
    TableOrderItem,
)


class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'cnpj', 'email', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'cnpj', 'email']
    readonly_fields = ['created_at', 'updated_at']


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


class TenantModelAdmin(admin.ModelAdmin):
    """
    Admin base para modelos com tenant
    """

    def get_queryset(self, request):
        """
        Filtra os objetos por empresa se o usuário não for superuser
        """
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        # Se o usuário tem perfil e empresa, filtra por essa empresa
        if hasattr(request.user, 'profile') and request.user.profile.company:
            return qs.filter(company=request.user.profile.company)

        # Se não tem empresa, não mostra nada
        return qs.none()

    def save_model(self, request, obj, form, change):
        """
        Define a empresa automaticamente ao salvar
        """
        if not change and hasattr(obj, 'company'):  # Novo objeto
            if hasattr(request.user, 'profile') and request.user.profile.company:
                obj.company = request.user.profile.company

        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        """
        Remove o campo company do formulário se o usuário não for superuser
        """
        form = super().get_form(request, obj, **kwargs)

        if not request.user.is_superuser and 'company' in form.base_fields:
            del form.base_fields['company']

        return form


class CategoryAdmin(TenantModelAdmin):
    list_display = ['name', 'description', 'status', 'company', 'date_added']
    list_filter = ['status', 'company']
    search_fields = ['name', 'description']


class ProductComboItemInline(admin.TabularInline):
    model = ProductComboItem
    extra = 1
    fields = ['component', 'quantity']
    verbose_name = 'Componente'
    verbose_name_plural = 'Componentes'
    fk_name = 'combo'


class ProductsAdmin(TenantModelAdmin):
    list_display = ['code', 'name', 'category_id',
                    'price', 'custo', 'status', 'company']
    list_filter = ['status', 'category_id', 'company']
    search_fields = ['code', 'name']
    inlines = [ProductComboItemInline]

    def get_inlines(self, request, obj=None):
        if obj and not obj.is_combo:
            return []
        return super().get_inlines(request, obj)


class SalesAdmin(TenantModelAdmin):
    list_display = [
        'code',
        'customer_name',
        'grand_total',
        'forma_pagamento',
        'venda_a_prazo',
        'type',
        'status',
        'company',
        'date_added',
    ]
    list_filter = ['forma_pagamento', 'venda_a_prazo', 'type',
                   'status', 'company', 'date_added']
    search_fields = ['code', 'customer_name']


class PedidoAdmin(TenantModelAdmin):
    list_display = ['code', 'customer_name', 'grand_total',
                    'forma_pagamento', 'status', 'company', 'date_added']
    list_filter = ['forma_pagamento', 'status', 'company', 'date_added']
    search_fields = ['code', 'customer_name']


class EstoqueAdmin(TenantModelAdmin):
    list_display = ['produto', 'quantidade', 'categoria',
                    'preco', 'custo', 'status', 'company']
    list_filter = ['status', 'categoria', 'company']
    search_fields = ['produto__name', 'produto__code']


class TableAdmin(TenantModelAdmin):
    list_display = ['number', 'name', 'capacity',
                    'is_active', 'waiter', 'company']
    list_filter = ['is_active', 'waiter', 'company']
    search_fields = ['number', 'name', 'waiter__name']


class TableOrderAdmin(TenantModelAdmin):
    list_display = ['id', 'table', 'status', 'total',
                    'waiter', 'opened_at', 'closed_at', 'company']
    list_filter = ['status', 'payment_method',
                   'waiter', 'company', 'opened_at']
    search_fields = ['table__number', 'waiter__name', 'waiter_name', 'id']


class TableOrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price', 'total']
    search_fields = ['order__id', 'product__name']
    list_select_related = ['order', 'product']


class GarcomAdmin(TenantModelAdmin):
    list_display = ['name', 'code', 'is_active', 'company', 'created_at']
    list_filter = ['is_active', 'company']
    search_fields = ['name', 'code']


# Registra os modelos
admin.site.register(Company, CompanyAdmin)

# Re-registra o User com o perfil inline
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Registra os modelos com tenant
admin.site.register(Category, CategoryAdmin)
admin.site.register(Products, ProductsAdmin)
admin.site.register(Sales, SalesAdmin)
admin.site.register(salesItems)  # Mantém o registro simples para salesItems
admin.site.register(Pedido, PedidoAdmin)
admin.site.register(Estoque, EstoqueAdmin)
admin.site.register(Garcom, GarcomAdmin)
admin.site.register(Table, TableAdmin)
admin.site.register(TableOrder, TableOrderAdmin)
admin.site.register(TableOrderItem, TableOrderItemAdmin)

# Configurações do admin
admin.site.site_header = 'Sistema Multi-Tenant'
admin.site.site_title = 'Admin Multi-Tenant'
admin.site.index_title = 'Painel de Administração'
