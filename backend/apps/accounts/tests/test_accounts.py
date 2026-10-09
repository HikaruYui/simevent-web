# Fungsi file: Pengujian app accounts: registrasi akun, login, session, CSRF, dan pencegahan privilege escalation.

from io import StringIO
from django.contrib import admin
from django.contrib.auth import authenticate
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.forms import RegistrationForm
from apps.accounts.models import User
from apps.accounts.permissions import require_organizer

PASSWORD = "a-Long-Unique-Password-932!"


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("bootstrap_roles", stdout=StringIO())
        cls.user = User.objects.create_user("andi@example.com", PASSWORD)

    def registration_data(self, **overrides):
        return {
            "email": "new@example.com",
            "first_name": "New",
            "password1": PASSWORD,
            "password2": PASSWORD,
            **overrides,
        }

    def test_default_participant_and_hashed_password(self):
        self.assertEqual(self.user.role, "PARTICIPANT")
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.groups.exists())
        self.assertNotEqual(self.user.password, PASSWORD)
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_email_normalization_and_case_insensitive_authentication(self):
        user = User.objects.create_user("  Other@EXAMPLE.COM  ", PASSWORD)
        self.assertEqual(user.email, "other@example.com")
        self.assertEqual(authenticate(email="OTHER@EXAMPLE.COM", password=PASSWORD), user)

    def test_database_rejects_case_variant_even_with_bulk_create(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="ANDI@example.com")])

    def test_database_rejects_empty_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="")])

    def test_superuser_creation_checks_flags(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser("admin@example.com", PASSWORD, is_staff=False)
        user = User.objects.create_superuser("admin@example.com", PASSWORD)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role, "ADMIN")

    def test_public_signup_ignores_privilege_fields(self):
        response = self.client.post(reverse("accounts:register"), self.registration_data(
            role="ADMIN", is_staff="true", is_superuser="true",
            groups=[Group.objects.get(name="Platform Admin").pk],
            user_permissions=[Permission.objects.get(codename="manage_platform").pk],
        ))
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.role, "PARTICIPANT")
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertFalse(user.groups.exists() or user.user_permissions.exists())

    def test_duplicate_signup_is_validation_error(self):
        response = self.client.post(reverse("accounts:register"), self.registration_data(
            email="ANDI@EXAMPLE.COM",
        ))
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])
        self.assertEqual(User.objects.count(), 1)

    def test_password_validation(self):
        form = RegistrationForm(data=self.registration_data(password1="123", password2="123"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_login_profile_logout(self):
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 401)
        response = self.client.post(reverse("accounts:login"), {
            "email": "ANDI@example.com", "password": PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.json()["email"], self.user.email)
        self.assertNotIn("password", response.json())
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 401)

    def test_login_rotates_session(self):
        session = self.client.session
        session["before_login"] = True
        session.save()
        old_key = session.session_key
        self.client.post(reverse("accounts:login"), {"email": self.user.email, "password": PASSWORD})
        self.assertNotEqual(self.client.session.session_key, old_key)

    def test_inactive_user_cannot_login_or_reuse_session(self):
        self.client.force_login(self.user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 401)
        response = self.client.post(reverse("accounts:login"), {"email": self.user.email, "password": PASSWORD})
        self.assertEqual(response.status_code, 400)

    def test_incorrect_password_and_unknown_email_have_same_error(self):
        known = self.client.post(reverse("accounts:login"), {"email": self.user.email, "password": "wrong"})
        unknown = self.client.post(reverse("accounts:login"), {"email": "missing@example.com", "password": "wrong"})
        self.assertEqual(known.json(), unknown.json())

    def test_mutations_reject_get(self):
        for name in ("register", "login", "logout"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"accounts:{name}")).status_code, 405)

    def test_csrf_is_required_for_all_auth_mutations(self):
        client = Client(enforce_csrf_checks=True)
        for name in ("register", "login", "logout"):
            with self.subTest(name=name):
                self.assertEqual(client.post(reverse(f"accounts:{name}"), {}).status_code, 403)
        token = client.get(reverse("accounts:csrf")).json()["csrf_token"]
        response = client.post(reverse("accounts:register"), self.registration_data(), HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)

    def test_participant_and_anonymous_fail_organizer_gate(self):
        for user in (self.user, AnonymousUser()):
            with self.subTest(user=user), self.assertRaises(PermissionDenied):
                require_organizer(user)

    def test_organizer_permission_can_be_revoked(self):
        group = Group.objects.get(name="Organizer")
        self.user.groups.add(group)
        user = User.objects.get(pk=self.user.pk)
        require_organizer(user)
        self.assertEqual(user.role, "ORGANIZER")
        self.assertFalse(user.has_perm("accounts.manage_platform"))
        self.user.groups.remove(group)
        with self.assertRaises(PermissionDenied):
            require_organizer(User.objects.get(pk=self.user.pk))

    def test_suspended_organizer_is_denied(self):
        self.user.groups.add(Group.objects.get(name="Organizer"))
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(PermissionDenied):
            require_organizer(self.user)

    def test_staff_flag_does_not_grant_platform_authority(self):
        self.user.is_staff = True
        self.user.save()
        self.assertEqual(self.user.role, "PARTICIPANT")
        with self.assertRaises(PermissionDenied):
            require_organizer(self.user)

    def test_bootstrap_is_idempotent_and_does_not_assign_users(self):
        original = Group.objects.count(), Permission.objects.count()
        call_command("bootstrap_roles", stdout=StringIO())
        self.assertEqual((Group.objects.count(), Permission.objects.count()), original)
        self.assertFalse(self.user.groups.exists())

    def test_generic_change_user_permission_cannot_escalate_privileges_in_admin(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename="change_user"))
        self.client.force_login(self.user)
        response = self.client.post(reverse("admin:accounts_user_change", args=[self.user.pk]), {
            "email": self.user.email, "is_superuser": "on", "is_staff": "on", "is_active": "on",
        })
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)

    def test_admin_create_user_form_uses_email(self):
        superuser = User.objects.create_superuser("admin@example.com", PASSWORD)
        request = RequestFactory().get("/admin/")
        request.user = superuser
        form_class = admin.site._registry[User].get_form(request, obj=None)
        form = form_class(data=self.registration_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().role, "PARTICIPANT")

