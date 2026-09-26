from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class BackendComLoja(ModelBackend):
    """ModelBackend que já traz a loja do usuário: toda tela da loja consulta `request.user.loja`,
    então carregá-la junto evita uma ida extra ao banco em cada requisição."""

    def get_user(self, user_id):
        modelo = get_user_model()
        try:
            user = modelo._default_manager.select_related('loja').get(pk=user_id)
        except modelo.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
