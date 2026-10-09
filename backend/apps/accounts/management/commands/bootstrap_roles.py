# Fungsi file: Perintah idempotent untuk menyiapkan Groups dan Permissions tanpa memberi role kepada user.

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Provision SIMEVENT groups after migrate; never assigns users to groups."

    @transaction.atomic
    def handle(self, *args, **options):
        roles = {
            "Organizer": (
                "accounts.access_organizer", "events.add_event", "events.view_event",
                "events.change_event", "events.delete_event", "events.submit_event",
                "events.complete_event", "events.cancel_event",
                "registrations.scan_ticket",
                "registrations.view_feedback",
                "achievements.view_achievement",
                "achievements.view_userachievement",
            ),
            "Platform Admin": (
                "accounts.manage_platform", "accounts.manage_organizer_access", "accounts.manage_accounts",
                "accounts.view_user", "accounts.view_accountaccesschange",
                "partnerships.review_proposal", "partnerships.view_organizerproposal", "partnerships.view_proposalreview",
                "events.add_event", "events.view_event", "events.change_event",
                "events.delete_event", "events.submit_event", "events.review_event",
                "events.publish_event", "events.complete_event", "events.cancel_event",
                "events.add_eventtype", "events.view_eventtype", "events.change_eventtype",
                "events.view_eventaccess", "events.view_eventtransition",
                "registrations.view_registration", "registrations.view_ticket",
                "registrations.view_attendance", "registrations.scan_ticket",
                "registrations.void_attendance",
                "registrations.view_feedback",
                "achievements.add_achievement", "achievements.view_achievement",
                "achievements.change_achievement", "achievements.view_userachievement",
                "achievements.add_reward", "achievements.change_reward",
                "achievements.view_reward", "achievements.view_eventrewardpolicy",
            ),
        }
        for name, codenames in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            for qualified_name in codenames:
                app_label, codename = qualified_name.split(".", 1)
                permission = Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
                group.permissions.add(permission)
        self.stdout.write(self.style.SUCCESS("SIMEVENT groups are ready."))
