from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from django.core.exceptions import PermissionDenied
from application.tenancy import filtrar_por_loja, loja_desativada, verificar_acesso_loja


def _usuario(is_superuser=False, loja=None):
    return SimpleNamespace(is_superuser=is_superuser, loja=loja)


def test_superusuario_sem_loja_tem_acesso():
    verificar_acesso_loja(_usuario(is_superuser=True))


def test_usuario_com_loja_ativa_tem_acesso():
    verificar_acesso_loja(_usuario(loja=SimpleNamespace(ativo=True)))


def test_usuario_sem_loja_e_negado():
    with pytest.raises(PermissionDenied, match="nenhuma loja"):
        verificar_acesso_loja(_usuario())


def test_usuario_de_loja_inativa_e_negado():
    with pytest.raises(PermissionDenied, match="desativada"):
        verificar_acesso_loja(_usuario(loja=SimpleNamespace(ativo=False)))


def test_filtrar_por_loja_restringe_usuario_comum():
    loja = object()
    queryset = Mock()

    resultado = filtrar_por_loja(queryset, _usuario(loja=loja))

    queryset.filter.assert_called_once_with(loja=loja)
    assert resultado is queryset.filter.return_value


def test_filtrar_por_loja_nao_restringe_superusuario():
    queryset = Mock()

    assert filtrar_por_loja(queryset, _usuario(is_superuser=True)) is queryset
    queryset.filter.assert_not_called()


def test_loja_desativada():
    assert loja_desativada(_usuario(loja=SimpleNamespace(ativo=False)))
    assert not loja_desativada(_usuario(loja=SimpleNamespace(ativo=True)))
    assert not loja_desativada(_usuario(is_superuser=True))


def test_filtrar_por_loja_por_campo_relacionado():
    loja = object()
    queryset = Mock()

    filtrar_por_loja(queryset, _usuario(loja=loja), campo='venda__loja')

    queryset.filter.assert_called_once_with(venda__loja=loja)
