from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.utils import get_user_company, guard_tables_ready
from p_v_App.models import Garcom
from staff.forms import GarcomForm


@login_required
def garcons(request):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request)
    if guard is not True:
        return guard

    waiters = Garcom.objects.filter(company=user_company).order_by('name')
    context = {
        'page_title': 'Garçons',
        'garcons': waiters,
        'garcom_form': GarcomForm(company=user_company),
        'current': 'garcons',
    }
    return render(request, 'staff/garcons.html', context)


@login_required
def salvar_garcom(request, garcom_id=None):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request, redirect_name='garcons')
    if guard is not True:
        return guard

    if request.method != 'POST':
        messages.error(request, 'Método inválido para salvar garçom.')
        return redirect('garcons')

    instance = None
    if garcom_id:
        instance = get_object_or_404(
            Garcom, pk=garcom_id, company=user_company)

    form = GarcomForm(request.POST, instance=instance, company=user_company)
    if form.is_valid():
        garcom = form.save(commit=False)
        garcom.company = user_company
        garcom.save()
        action = 'atualizado' if instance else 'cadastrado'
        messages.success(
            request, f'Garçom {garcom.name} {action} com sucesso.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    redirect_target = request.POST.get('next') or reverse('garcons')
    return redirect(redirect_target)


@login_required
def excluir_garcom(request, garcom_id):
    user_company = get_user_company(request)
    if not user_company:
        messages.error(
            request, 'Usuário não está associado a nenhuma empresa.')
        return redirect('home-page')

    guard = guard_tables_ready(request, redirect_name='garcons')
    if guard is not True:
        return guard

    garcom = get_object_or_404(Garcom, pk=garcom_id, company=user_company)

    if request.method != 'POST':
        messages.error(request, 'Método inválido para excluir garçom.')
        return redirect('garcons')

    try:
        garcom.delete()
        messages.success(request, 'Garçom removido com sucesso.')
    except ProtectedError:
        messages.error(
            request,
            'Não é possível excluir o garçom pois existem comandas vinculadas a ele. Desative-o em vez de excluir.',
        )

    redirect_target = request.POST.get('next') or reverse('garcons')
    return redirect(redirect_target)
