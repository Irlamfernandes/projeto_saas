import calendar
from datetime import timedelta
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# O agendador chama de hora em hora, mas às vezes atrasa alguns minutos. Sem folga, um backup "a cada 1 hora"
# feito às 10:07 perderia a chamada das 11:03 e só sairia ao meio-dia.
FOLGA = timedelta(minutes=30)
NOME_DA_CONFIGURACAO = 'Configuração de backup'


class UnidadeDoIntervalo(models.TextChoices):
    HORAS = 'horas', 'Horas'
    DIAS = 'dias', 'Dias'
    MESES = 'meses', 'Meses'


def somar_intervalo(momento, quantidade, unidade):
    """`momento` + N horas, dias ou meses (mês a mês: 31/01 + 1 mês = 28 ou 29/02)."""
    if unidade == UnidadeDoIntervalo.HORAS:
        return momento + timedelta(hours=quantidade)
    if unidade == UnidadeDoIntervalo.DIAS:
        return momento + timedelta(days=quantidade)
    meses = momento.month - 1 + quantidade
    ano, mes = momento.year + meses // 12, meses % 12 + 1
    return momento.replace(year=ano, month=mes, day=min(momento.day, calendar.monthrange(ano, mes)[1]))


class ConfiguracaoDeBackup(models.Model):
    """Uma só linha (pk=1), editada no admin. O agendador chama o sistema de hora em hora; o backup só é
    feito quando está ligado e já passou o intervalo desde o último que deu certo."""
    ativo = models.BooleanField("Backup automático ligado", default=False)
    a_cada = models.PositiveSmallIntegerField("A cada", default=1, validators=[MinValueValidator(1)])
    unidade = models.CharField(max_length=5, choices=UnidadeDoIntervalo.choices, default=UnidadeDoIntervalo.DIAS)
    manter = models.PositiveSmallIntegerField(
        "Cópias guardadas", default=30, validators=[MinValueValidator(1)],
        help_text="Ao passar deste número, as cópias mais antigas são apagadas.",
    )
    ultimo_em = models.DateTimeField("Último backup que deu certo", null=True, blank=True)
    em_andamento_desde = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'configuracao_de_backup'
        verbose_name = NOME_DA_CONFIGURACAO
        verbose_name_plural = NOME_DA_CONFIGURACAO

    def __str__(self):
        return NOME_DA_CONFIGURACAO

    @classmethod
    def atual(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def proximo_em(self):
        """Quando o próximo backup automático acontece. None: desligado ou nunca feito (aí é na próxima chamada)."""
        if not self.ativo or self.ultimo_em is None:
            return None
        return somar_intervalo(self.ultimo_em, self.a_cada, self.unidade)

    def esta_na_hora(self, agora):
        return self.ativo and (self.ultimo_em is None or agora + FOLGA >= self.proximo_em())


class OrigemDoBackup(models.TextChoices):
    AGENDADO = 'agendado', 'Agendado'
    MANUAL = 'manual', 'Manual'


class Backup(models.Model):
    """Uma cópia dos dados: arquivo compactado e criptografado no bucket privado `backups` do Supabase."""
    criado_em = models.DateTimeField(db_index=True)
    origem = models.CharField(max_length=10, choices=OrigemDoBackup.choices)
    arquivo = models.CharField(max_length=200, blank=True)
    tamanho = models.PositiveBigIntegerField(default=0, help_text="Em bytes, já compactado e criptografado.")
    registros = models.PositiveIntegerField(default=0)
    duracao = models.DurationField(null=True, blank=True)
    sucesso = models.BooleanField(default=False)
    erro = models.TextField(blank=True)

    class Meta:
        db_table = 'backups'
        verbose_name = 'Backup'
        verbose_name_plural = 'Backups'
        ordering = ['-criado_em']

    def __str__(self):
        return self.arquivo or f"Backup de {timezone.localtime(self.criado_em):%d/%m/%Y %H:%M}"
