"""Quem desenvolveu o sistema (CorsariosCode): dados usados no login, no rodapé, no suporte e nos relatórios.

Para mudar um contato, altere só aqui. Campo vazio esconde o botão correspondente.
"""
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class Desenvolvedor:
    nome: str
    frase: str
    whatsapp: str  # só números, com DDI e DDD
    instagram: str  # sem o @; vazio até ter a conta

    @property
    def whatsapp_formatado(self):
        ddd, numero = self.whatsapp[2:4], self.whatsapp[4:]
        return f"({ddd}) {numero[:-4]}-{numero[-4:]}"

    @property
    def link_whatsapp(self):
        return f"https://wa.me/{self.whatsapp}" if self.whatsapp else ''

    @property
    def link_instagram(self):
        return f"https://instagram.com/{self.instagram}" if self.instagram else ''

    @property
    def assinatura(self):
        """Crédito pequeno no rodapé dos relatórios em PDF (o extrato do cliente não leva)."""
        partes = [f"Sistema {self.nome}"]
        if self.instagram:
            partes.append(f"@{self.instagram}")
        return ' · '.join(partes)

    @property
    def link_nova_loja(self):
        """Para quem ainda não tem acesso: pedido de cadastro de loja nova, já escrito."""
        return self._whatsapp_com_mensagem("Olá! Quero liberar o acesso da minha loja ao sistema de gestão.")

    def link_suporte(self, nome_da_loja):
        """WhatsApp com a mensagem já escrita: você recebe sabendo de qual loja é o pedido."""
        return self._whatsapp_com_mensagem(f"Olá! Sou da loja {nome_da_loja} e preciso de ajuda com o sistema.")

    def _whatsapp_com_mensagem(self, mensagem):
        if not self.whatsapp:
            return ''
        return f"{self.link_whatsapp}?text={quote(mensagem)}"


CORSARIOS_CODE = Desenvolvedor(
    nome='CorsariosCode',
    frase='Desenvolvimento de software',
    whatsapp='5524992248899',
    instagram='',
)
