# Fungsi file: Pengujian app accounts: pemberian/pencabutan akses Organizer, suspend/activate, dan audit akun.

from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from apps.accounts.models import AccountAccessChange, User
from apps.accounts.services import change_account_access


class AccessManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command(
            "bootstrap_roles",
            stdout=StringIO(),
        )

        cls.admin = User.objects.create_user(
            "admin@example.com",
            "test-password",
            is_staff=True,
        )

        cls.admin.groups.add(
            Group.objects.get(
                name="Platform Admin"
            )
        )

        cls.user = User.objects.create_user(
            "participant@example.com",
            "test-password",
        )

    def change(
        self,
        action,
        reason="Administrative review",
    ):
        return change_account_access(
            actor=self.admin,
            user_id=self.user.pk,
            action=action,
            reason=reason,
        )

    def test_grant_and_revoke_have_actor_reason_and_no_staff_escalation(
        self,
    ):
        entry = self.change(
            AccountAccessChange.Action.GRANT_ORGANIZER
        )

        self.assertEqual(
            entry.actor,
            self.admin,
        )

        self.assertEqual(
            entry.reason,
            "Administrative review",
        )

        user = User.objects.get(
            pk=self.user.pk
        )

        self.assertEqual(
            user.role,
            "ORGANIZER",
        )

        self.assertFalse(
            user.is_staff
        )

        self.change(
            AccountAccessChange.Action.REVOKE_ORGANIZER
        )

        user = User.objects.get(pk=user.pk)

        self.assertEqual(
            user.role,
            "PARTICIPANT",
        )

        self.assertEqual(
            AccountAccessChange.objects.count(),
            2,
        )

    def test_grant_twice_does_not_duplicate_audit(
        self,
    ):
        self.change(
            AccountAccessChange.Action.GRANT_ORGANIZER
        )

        with self.assertRaises(ValidationError):
            self.change(
                AccountAccessChange.Action.GRANT_ORGANIZER
            )

        self.assertEqual(
            AccountAccessChange.objects.count(),
            1,
        )

    def test_access_audit_failure_rolls_back_group(
        self,
    ):
        with patch(
            "apps.accounts.services."
            "AccountAccessChange.objects.create",
            side_effect=RuntimeError(
                "audit failure"
            ),
        ):
            with self.assertRaises(RuntimeError):
                self.change(
                    AccountAccessChange.Action.GRANT_ORGANIZER
                )

        self.assertFalse(
            self.user.groups.exists()
        )

    def test_reason_and_action_are_validated(
        self,
    ):
        with self.assertRaises(ValidationError):
            self.change(
                AccountAccessChange.Action.GRANT_ORGANIZER,
                reason=" ",
            )

        with self.assertRaises(ValidationError):
            self.change(
                "PROMOTE_ADMIN"
            )

        self.assertFalse(
            AccountAccessChange.objects.exists()
        )

    def test_suspend_blocks_existing_session_and_activation_restores_login(
        self,
    ):
        client = Client()

        client.force_login(
            self.user
        )

        self.change(
            AccountAccessChange.Action.SUSPEND
        )

        response = client.get(
            reverse("accounts:profile")
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        with self.assertRaises(ValidationError):
            self.change(
                AccountAccessChange.Action.GRANT_ORGANIZER
            )

        self.change(
            AccountAccessChange.Action.ACTIVATE
        )

        self.assertTrue(
            client.login(
                email=self.user.email,
                password="test-password",
            )
        )

        self.assertEqual(
            AccountAccessChange.objects.count(),
            2,
        )

    def test_staff_flag_and_single_permission_are_insufficient(
        self,
    ):
        self.user.is_staff = True
        self.user.save()

        self.user.user_permissions.add(
            Permission.objects.get(
                codename="manage_organizer_access"
            )
        )

        with self.assertRaises(PermissionDenied):
            change_account_access(
                actor=self.user,
                user_id=self.admin.pk,
                action=(
                    AccountAccessChange.Action
                    .REVOKE_ORGANIZER
                ),
                reason="Attempt",
            )

    def test_stale_admin_permissions_are_refreshed(
        self,
    ):
        self.assertTrue(
            self.admin.has_perm(
                "accounts.manage_organizer_access"
            )
        )

        self.admin.groups.clear()

        with self.assertRaises(PermissionDenied):
            self.change(
                AccountAccessChange.Action.GRANT_ORGANIZER
            )

    def test_cannot_manage_self_or_other_admin_even_when_inactive(
        self,
    ):
        with self.assertRaises(PermissionDenied):
            change_account_access(
                actor=self.admin,
                user_id=self.admin.pk,
                action=(
                    AccountAccessChange.Action.SUSPEND
                ),
                reason="Attempt",
            )

        self.user.groups.add(
            Group.objects.get(
                name="Platform Admin"
            )
        )

        self.user.is_active = False
        self.user.save()

        with self.assertRaises(PermissionDenied):
            self.change(
                AccountAccessChange.Action.ACTIVATE
            )

    def test_revoke_removes_direct_permission_too(
        self,
    ):
        self.change(
            AccountAccessChange.Action.GRANT_ORGANIZER
        )

        self.user.user_permissions.add(
            Permission.objects.get(
                codename="access_organizer"
            )
        )

        self.change(
            AccountAccessChange.Action.REVOKE_ORGANIZER
        )

        user = User.objects.get(
            pk=self.user.pk
        )

        self.assertFalse(
            user.has_perm(
                "accounts.access_organizer"
            )
        )

    def test_revoke_refuses_silent_success_with_alternate_group(
        self,
    ):
        extra = Group.objects.create(
            name="Unexpected organizer source"
        )

        extra.permissions.add(
            Permission.objects.get(
                codename="access_organizer"
            )
        )

        self.user.groups.add(
            extra
        )

        with self.assertRaises(ValidationError):
            self.change(
                AccountAccessChange.Action.REVOKE_ORGANIZER
            )

        self.assertFalse(
            AccountAccessChange.objects.exists()
        )

    def test_native_admin_action_requires_confirmation_and_logs_change(
        self,
    ):
        self.client.force_login(
            self.admin
        )

        url = reverse(
            "admin:accounts_user_changelist"
        )

        data = {
            "action": "grant_organizer",
            "_selected_action": str(
                self.user.pk
            ),
            "reason": "Approved manually",
        }

        response = self.client.post(
            url,
            data,
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertFalse(
            AccountAccessChange.objects.exists()
        )

        response = self.client.post(
            url,
            {
                **data,
                "confirm": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            AccountAccessChange.objects.get().action,
            AccountAccessChange.Action.GRANT_ORGANIZER,
        )

    def test_access_logs_are_read_only_in_admin(
        self,
    ):
        entry = self.change(
            AccountAccessChange.Action.GRANT_ORGANIZER
        )

        self.client.force_login(
            self.admin
        )

        change_url = reverse(
            "admin:accounts_accountaccesschange_change",
            args=[entry.pk],
        )

        delete_url = reverse(
            "admin:accounts_accountaccesschange_delete",
            args=[entry.pk],
        )

        self.assertEqual(
            self.client.get(
                change_url
            ).status_code,
            200,
        )

        self.assertEqual(
            self.client.post(
                change_url,
                {"reason": "tamper"},
            ).status_code,
            403,
        )

        self.assertEqual(
            self.client.post(
                delete_url
            ).status_code,
            403,
        )

    def test_unauthorized_staff_cannot_use_admin_action(
        self,
    ):
        self.user.is_staff = True
        self.user.save()

        self.user.user_permissions.add(
            Permission.objects.get(
                codename="view_user"
            )
        )

        self.client.force_login(
            self.user
        )

        response = self.client.post(
            reverse(
                "admin:accounts_user_changelist"
            ),
            {
                "action": "grant_organizer",
                "_selected_action": str(
                    self.user.pk
                ),
                "reason": "Attempt",
                "confirm": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertFalse(
            AccountAccessChange.objects.exists()
        )
