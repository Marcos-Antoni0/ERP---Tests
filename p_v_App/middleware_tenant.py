from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from .models_tenant import get_current_company
from .models import *


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware que configura o contexto de tenant (empresa) para cada requisição
    """

    def process_request(self, request):
        # Define a empresa atual com base no usuário logado
        if request.user.is_authenticated:
            try:
                company = get_current_company(request)
                if company:
                    # Define a empresa no contexto da requisição
                    request.current_company = company

                    # Configura os managers para filtrar por empresa
                    Category.objects = Category.objects.set_company(company)
                    Products.objects = Products.objects.set_company(company)
                    Sales.objects = Sales.objects.set_company(company)
                    Pedido.objects = Pedido.objects.set_company(company)
                    Estoque.objects = Estoque.objects.set_company(company)
                else:
                    # Usuário não tem empresa associada
                    request.current_company = None
            except Exception:
                # Em caso de erro, não define empresa
                request.current_company = None
        else:
            request.current_company = None

        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Processa a view para garantir que apenas usuários com empresa possam acessar
        """
        # Lista de views que não precisam de empresa (login, logout, etc.)
        exempt_views = [
            'login_user',
            'logout_user',
            'admin:index',
            'admin:login',
            'admin:logout',
        ]

        # Obtém o nome da view
        view_name = getattr(view_func, '__name__', '')

        # Se é uma view do admin, permite acesso
        if view_name.startswith('admin') or 'admin' in request.path:
            return None

        # Se é uma view isenta, permite acesso
        if view_name in exempt_views:
            return None

        # Se o usuário não está autenticado, permite que o Django redirecione para login
        if not request.user.is_authenticated:
            return None

        # Se o usuário está logado mas não tem empresa
        if not hasattr(request, 'current_company') or request.current_company is None:
            # Só redireciona se não estiver já no admin
            if not request.path.startswith('/admin/'):
                messages.error(
                    request, 'Usuário não está associado a nenhuma empresa.')
                return redirect('/admin/')

        return None


class TenantQuerySetMixin:
    """
    Mixin para automaticamente filtrar querysets por tenant
    """

    def get_queryset(self):
        """
        Sobrescreve get_queryset para filtrar por empresa atual
        """
        queryset = super().get_queryset()

        # Obtém a empresa atual da requisição
        if hasattr(self.request, 'current_company') and self.request.current_company:
            if hasattr(queryset.model, 'company'):
                queryset = queryset.filter(
                    company=self.request.current_company)

        return queryset

    def form_valid(self, form):
        """
        Sobrescreve form_valid para definir a empresa antes de salvar
        """
        if hasattr(self.request, 'current_company') and self.request.current_company:
            if hasattr(form.instance, 'company'):
                form.instance.company = self.request.current_company

        return super().form_valid(form)


def tenant_required(view_func):
    """
    Decorator que garante que o usuário tenha uma empresa associada
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if not hasattr(request, 'current_company') or not request.current_company:
            messages.error(
                request, 'Usuário não está associado a nenhuma empresa.')
            return redirect('admin:index')

        return view_func(request, *args, **kwargs)

    return wrapper


class TenantAwareModelMixin:
    """
    Mixin para modelos que precisam ser conscientes do tenant
    """

    def save(self, *args, **kwargs):
        # Se não tem empresa definida, tenta obter do contexto
        if not hasattr(self, 'company') or not self.company:
            if hasattr(self, '_current_company'):
                self.company = self._current_company

        super().save(*args, **kwargs)

    @classmethod
    def create_for_company(cls, company, **kwargs):
        """
        Método de classe para criar instâncias com empresa definida
        """
        instance = cls(**kwargs)
        instance.company = company
        return instance
