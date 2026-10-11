from django.apps import AppConfig


class InfrastructureConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'infrastructure'
    verbose_name = 'Gestão'

    def ready(self):
        # Fotos HEIC/HEIF (padrão do iPhone e de vários Androids): o Pillow passa a abri-las como qualquer outra.
        from pi_heif import register_heif_opener
        register_heif_opener()
