from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from application.contas.tentativas import esquecer_falhas, minutos_bloqueado, registrar_falha


class BackendComLoja(ModelBackend):
    """ModelBackend que já traz a loja do usuário: toda tela da loja consulta `request.user.loja`,
    então carregá-la junto evita uma ida extra ao banco em cada requisição.

    Também barra quem erra a senha várias vezes seguidas (vale para o login do site e o do admin).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if not username:
            return None
        if minutos_bloqueado(username):
            # Bloqueado: nem confere a senha. PermissionDenied encerra a autenticação sem tentar outro backend.
            raise PermissionDenied
        user = super().authenticate(request, username=username, password=password, **kwargs)
        if user is None:
            registrar_falha(username)
        else:
            esquecer_falhas(username)
        return user

    def get_user(self, user_id):
        modelo = get_user_model()
        try:
            user = modelo._default_manager.select_related('loja').get(pk=user_id)
        except modelo.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
