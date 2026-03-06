from django.apps import AppConfig


class InviteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invite'

    def ready(self):
        import invite.signals  # noqa: F401
