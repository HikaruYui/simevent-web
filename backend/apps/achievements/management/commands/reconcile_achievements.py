# Fungsi file: Perintah operator untuk menyelaraskan achievement dengan kehadiran valid terkini.

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.achievements.services import AchievementService


class Command(BaseCommand):
    help = "Evaluate active achievements for one user or all active users."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int)

    def handle(self, *args, **options):
        user_id = options["user_id"]
        if user_id:
            user = User.objects.filter(pk=user_id, is_active=True).first()
            if user is None:
                raise CommandError("Active user was not found.")
            # A trusted maintenance command may evaluate a target directly.
            assignments = AchievementService(user).evaluate()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Evaluated {len(assignments)} active achievements for user {user_id}."
                )
            )
            return
        total = 0
        for user in User.objects.filter(is_active=True).only("pk"):
            total += len(AchievementService(user).evaluate())
        self.stdout.write(self.style.SUCCESS(f"Evaluated active achievements ({total} assignments)."))
