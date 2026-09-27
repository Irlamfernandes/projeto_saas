from urllib.parse import unquote
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from interfaces.context_processors import desenvolvedor
from interfaces.desenvolvedor import CORSARIOS_CODE, Desenvolvedor
from infrastructure.models import LojaModel

WHATSAPP = "https://wa.me/5524992248899"


class DesenvolvedorTest(SimpleTestCase):

    def test_contatos_da_corsarioscode(self):
        self.assertEqual(CORSARIOS_CODE.nome, "CorsariosCode")
        self.assertEqual(CORSARIOS_CODE.whatsapp_formatado, "(24) 99224-8899")
        self.assertEqual(CORSARIOS_CODE.link_whatsapp, WHATSAPP)

    def test_suporte_ja_manda_o_nome_da_loja_na_mensagem(self):
        link = CORSARIOS_CODE.link_suporte("Padaria Pão & Mel")
        self.assertTrue(link.startswith(f"{WHATSAPP}?text="))
        self.assertEqual(unquote(link.split('text=')[1]), "Olá! Sou da loja Padaria Pão & Mel e preciso de ajuda com o sistema.")

    def test_pedido_de_loja_nova_ja_vem_escrito(self):
        link = CORSARIOS_CODE.link_nova_loja
        self.assertTrue(link.startswith(f"{WHATSAPP}?text="))
        self.assertEqual(unquote(link.split('text=')[1]), "Olá! Quero liberar o acesso da minha loja ao sistema de gestão.")

    def test_instagram_vazio_some_e_preenchido_aparece(self):
        sem = Desenvolvedor(nome="X", frase="", whatsapp="", instagram="")
        com = Desenvolvedor(nome="X", frase="", whatsapp="5511999998888", instagram="corsarioscode")
        self.assertEqual((sem.link_instagram, sem.link_whatsapp, sem.link_suporte("Loja"), sem.link_nova_loja), ('', '', '', ''))
        self.assertEqual(com.link_instagram, "https://instagram.com/corsarioscode")
        self.assertEqual(sem.assinatura, "Sistema X")
        self.assertEqual(com.assinatura, "Sistema X · @corsarioscode")

    def test_context_processor(self):
        self.assertEqual(desenvolvedor(None), {'desenvolvedor': CORSARIOS_CODE})


class RodapesTest(TestCase):

    def test_login_tem_a_vitrine_com_logo_e_whatsapp(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'images/corsarioscode-emblema')
        self.assertContains(response, f'href="{WHATSAPP}"')
        self.assertContains(response, 'rel="noopener"')
        self.assertNotContains(response, "instagram.com")  # ainda sem Instagram

    def test_login_mostra_a_apresentacao_uma_vez_so_para_celular_e_pc(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, "Vendas, estoque e caderneta num lugar só.", count=1)
        self.assertNotContains(response, 'hidden lg:flex flex-col justify-between')  # não fica mais escondida no celular

    def test_login_tem_o_pedido_de_cadastro_de_loja_nova(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, "Quero cadastrar minha loja")
        self.assertContains(response, CORSARIOS_CODE.link_nova_loja)

    def test_troca_de_senha_tem_o_mesmo_rodape_do_login(self):
        loja = LojaModel.objects.create(nome_loja="Padaria")
        self.client.force_login(get_user_model().objects.create_user(username="novo", password="x", loja=loja, deve_trocar_senha=True))
        response = self.client.get(reverse('alterar_senha'))
        self.assertContains(response, 'images/corsarioscode-emblema')
        self.assertContains(response, f'href="{WHATSAPP}"')

    def test_paginas_do_sistema_tem_o_rodape_discreto(self):
        loja = LojaModel.objects.create(nome_loja="Padaria")
        self.client.force_login(get_user_model().objects.create_user(username="c", password="x", loja=loja, deve_trocar_senha=False))
        for rota in ('dashboard', 'vendas', 'configuracoes'):
            with self.subTest(rota):
                response = self.client.get(reverse(rota))
                self.assertContains(response, "Sistema feito por")
                self.assertContains(response, 'aria-label="WhatsApp da CorsariosCode"')

    def test_configuracoes_tem_suporte_com_o_nome_da_loja(self):
        loja = LojaModel.objects.create(nome_loja="Padaria Sol")
        self.client.force_login(get_user_model().objects.create_user(username="c", password="x", loja=loja, deve_trocar_senha=False))
        response = self.client.get(reverse('configuracoes'))
        self.assertContains(response, "Falar no WhatsApp")
        self.assertContains(response, CORSARIOS_CODE.link_suporte("Padaria Sol"))
        self.assertContains(response, "(24) 99224-8899")

    def test_superusuario_ve_suporte_como_painel_global(self):
        self.client.force_login(get_user_model().objects.create_superuser(username="admin", password="x", deve_trocar_senha=False))
        self.assertContains(self.client.get(reverse('configuracoes')), CORSARIOS_CODE.link_suporte("Painel global"))
