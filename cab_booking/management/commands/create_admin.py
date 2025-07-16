from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = "Create a default superuser if not exists"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        username = "admin"
        password = "admin1234"
        email = "admin@zipcab.com"

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created!"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists."))
