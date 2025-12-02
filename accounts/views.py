import json

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.shortcuts import redirect

from p_v_App.middleware import UserSessionTracker


def login_user(request):
    logout(request)
    resp = {'status': 'failed', 'msg': ''}
    username = ''
    password = ''

    if request.POST:
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')

        user = authenticate(username=username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            UserSessionTracker.invalidate_other_sessions(
                user, request.session.session_key)
            resp['status'] = 'success'
        else:
            resp['msg'] = 'Nome de usuário ou senha incorretos'

    return HttpResponse(json.dumps(resp), content_type='application/json')


def logout_user(request):
    logout(request)
    return redirect('home-page')
