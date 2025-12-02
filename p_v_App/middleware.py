from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone


class SingleSessionMiddleware(MiddlewareMixin):
    """
    Middleware que garante que cada usuário tenha apenas uma sessão ativa por vez.
    Se um usuário fizer login em outro lugar, a sessão anterior será invalidada.
    """

    def process_request(self, request):
        if request.user.is_authenticated:
            # Obtém a chave da sessão atual
            current_session_key = request.session.session_key

            # Busca todas as sessões ativas para este usuário
            user_sessions = Session.objects.filter(
                expire_date__gte=timezone.now()
            )

            # Verifica se há outras sessões para este usuário
            for session in user_sessions:
                session_data = session.get_decoded()
                if session_data.get('_auth_user_id') == str(request.user.id):
                    # Se encontrou uma sessão diferente da atual para o mesmo usuário
                    if session.session_key != current_session_key:
                        # Remove a sessão anterior
                        session.delete()

            # Verifica se a sessão atual ainda é válida
            try:
                current_session = Session.objects.get(
                    session_key=current_session_key)
                session_data = current_session.get_decoded()

                # Se a sessão não pertence mais ao usuário atual, faz logout
                if session_data.get('_auth_user_id') != str(request.user.id):
                    logout(request)
                    messages.warning(
                        request, 'Sua sessão foi encerrada porque você fez login em outro dispositivo.')
                    return HttpResponseRedirect(reverse('login'))

            except Session.DoesNotExist:
                # Se a sessão atual não existe mais, faz logout
                logout(request)
                messages.warning(
                    request, 'Sua sessão foi encerrada porque você fez login em outro dispositivo.')
                return HttpResponseRedirect(reverse('login'))

        return None


class UserSessionTracker:
    """
    Classe auxiliar para rastrear sessões de usuários
    """

    @staticmethod
    def invalidate_other_sessions(user, current_session_key):
        """
        Invalida todas as outras sessões de um usuário, mantendo apenas a atual
        """
        from django.utils import timezone

        user_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        )

        for session in user_sessions:
            session_data = session.get_decoded()
            if (session_data.get('_auth_user_id') == str(user.id) and
                    session.session_key != current_session_key):
                session.delete()

    @staticmethod
    def get_active_sessions_count(user):
        """
        Retorna o número de sessões ativas para um usuário
        """
        from django.utils import timezone

        count = 0
        user_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        )

        for session in user_sessions:
            session_data = session.get_decoded()
            if session_data.get('_auth_user_id') == str(user.id):
                count += 1

        return count
