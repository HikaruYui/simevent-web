# Fungsi file: Proses pembuatan, perubahan, transisi status, dan penghapusan draft event dengan izin serta audit.
from uuid import uuid4
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from apps.accounts.models import User
from apps.accounts.permissions import require_organizer
from apps.accounts.services import lock_accounts, require_platform_permission
from .forms import AdminEventForm, EventForm
from .models import DeliveryMode, Event, EventAccess, EventStatus, EventTransition


# Encapsulation: aturan izin, ownership, status, dan audit dirangkum di dalam workflow.
class EventWorkflow:
    """Authorize and commit event changes and their audit trail as one operation."""

    transitions = {
        EventStatus.SUBMITTED: {EventStatus.DRAFT, EventStatus.NEEDS_REVISION},
        EventStatus.NEEDS_REVISION: {EventStatus.SUBMITTED, EventStatus.APPROVED},
        EventStatus.APPROVED: {EventStatus.SUBMITTED, EventStatus.PUBLISHED},
        EventStatus.PUBLISHED: {EventStatus.APPROVED},
        EventStatus.REJECTED: {EventStatus.SUBMITTED},
        EventStatus.COMPLETED: {EventStatus.PUBLISHED},
        EventStatus.CANCELLED: {
            EventStatus.DRAFT, EventStatus.SUBMITTED, EventStatus.NEEDS_REVISION,
            EventStatus.APPROVED, EventStatus.PUBLISHED,
        },
    }
    permissions = {
        EventStatus.SUBMITTED: "events.submit_event",
        EventStatus.NEEDS_REVISION: "events.review_event",
        EventStatus.APPROVED: "events.review_event",
        EventStatus.PUBLISHED: "events.publish_event",
        EventStatus.REJECTED: "events.review_event",
        EventStatus.COMPLETED: "events.complete_event",
        EventStatus.CANCELLED: "events.cancel_event",
    }
    admin_decisions = {
        EventStatus.NEEDS_REVISION, EventStatus.APPROVED,
        EventStatus.PUBLISHED, EventStatus.REJECTED,
    }
    action_targets = {
        "submit": EventStatus.SUBMITTED,
        "request_revision": EventStatus.NEEDS_REVISION,
        "approve": EventStatus.APPROVED,
        "publish": EventStatus.PUBLISHED,
        "unpublish": EventStatus.APPROVED,
        "reject": EventStatus.REJECTED,
        "complete": EventStatus.COMPLETED,
        "cancel": EventStatus.CANCELLED,
    }

    def __init__(self, actor):
        if not actor.is_authenticated:
            raise PermissionDenied
        self._actor_id = actor.pk

    def _actor(self):
        actor = get_object_or_404(User, pk=self._actor_id)
        require_organizer(actor)
        return actor

    @staticmethod
    def _require(actor, permission):
        require_organizer(actor)
        if not actor.has_perm(permission):
            raise PermissionDenied

    def _lock_event(self, event_id):
        actor = self._actor()
        visible = get_object_or_404(Event.objects.managed_by(actor), pk=event_id)
        users = lock_accounts(actor.pk, visible.organizer_id)
        actor = users[actor.pk]
        require_organizer(actor)
        event = get_object_or_404(
            Event.objects.managed_by(actor).select_for_update(), pk=event_id
        )
        return actor, event, users[event.organizer_id]

    @staticmethod
    def _valid_form(form):
        if not form.is_valid():
            raise ValidationError(form.errors.as_data())

    @staticmethod
    def _save_content(form, previous_banner=""):
        event = form.save(commit=False)
        if form.cleaned_data["remove_banner"]:
            event.banner = ""
        storage = event.banner.storage
        try:
            with transaction.atomic():
                event.save()
                EventAccess.objects.update_or_create(
                    event=event,
                    defaults={
                        "meeting_url": form.cleaned_data["meeting_url"],
                        "instructions": form.cleaned_data["access_instructions"],
                    },
                )
        except Exception:
            # File storage does not participate in the database transaction.
            if (
                event.banner.name
                and event.banner.name != previous_banner
                and event.banner._committed
            ):
                storage.delete(event.banner.name)
            raise
        if previous_banner and previous_banner != event.banner.name:
            transaction.on_commit(lambda: storage.delete(previous_banner), robust=True)
        return event

    @transaction.atomic
    def create(self, *, data, files=None):
        actor = self._actor()
        self._require(actor, "events.add_event")
        form_class = (
            AdminEventForm if actor.has_perm("accounts.manage_platform") else EventForm
        )
        form = form_class(data, files, instance=Event(organizer=actor))
        self._valid_form(form)
        owner = form.cleaned_data.get("organizer", actor)
        users = lock_accounts(actor.pk, owner.pk)
        self._require(users[actor.pk], "events.add_event")
        if owner.pk != actor.pk:
            require_platform_permission(users[actor.pk], "events.add_event")
        owner = users[owner.pk]
        if not owner.is_active or not owner.has_perm("accounts.access_organizer"):
            raise ValidationError("Choose an active organizer as the event owner.")
        form.instance.organizer = owner
        title_slug = slugify(form.cleaned_data["title"])[:180] or "event"
        form.instance.slug = f"{title_slug}-{uuid4().hex}"
        return self._save_content(form)

    @transaction.atomic
    def update(self, event_id, *, data, files=None):
        actor, event, _ = self._lock_event(event_id)
        self._require(actor, "events.change_event")
        if not event.is_editable:
            raise ValidationError("Only draft or revision events can be edited.")
        previous_banner = event.banner.name
        form = EventForm(data, files, instance=event)
        self._valid_form(form)
        if event.registrations.active().count() > event.capacity:
            raise ValidationError({"capacity": "Capacity cannot be below active registrations."})
        return self._save_content(form, previous_banner)

    @staticmethod
    def _validate_ready(event, owner):
        event.full_clean()
        if not owner.is_active or not owner.has_perm("accounts.access_organizer"):
            raise ValidationError("The event owner must have active organizer access.")
        if not event.event_type.is_active:
            raise ValidationError("This event type is inactive.")
        if event.start_datetime <= timezone.now():
            raise ValidationError("The event must start in the future.")
        if event.price != 0:
            raise ValidationError("Paid events remain drafts until payment is supported.")
        if (
            event.delivery_mode in (DeliveryMode.OFFLINE, DeliveryMode.HYBRID)
            and not event.venue.strip()
        ):
            raise ValidationError({"venue": "An offline or hybrid event requires a venue."})
        if event.delivery_mode in (DeliveryMode.ONLINE, DeliveryMode.HYBRID):
            access = EventAccess.objects.filter(event=event).first()
            if not access or not access.meeting_url:
                raise ValidationError({
                    "meeting_url": "An online or hybrid event requires meeting access."
                })
            access.full_clean()

    def _validate_transition(self, actor, event, owner, action, reason):
        target = self.action_targets.get(action)
        if target is None:
            raise ValidationError("Unknown event transition.")
        permission = self.permissions[target]
        if action == "unpublish":
            permission = "events.publish_event"
        if target in self.admin_decisions:
            require_platform_permission(actor, permission)
        else:
            self._require(actor, permission)
        if event.status not in self.transitions[target]:
            raise ValidationError("This transition is not allowed from the current state.")
        if target == EventStatus.APPROVED:
            expected = (
                EventStatus.PUBLISHED if action == "unpublish" else EventStatus.SUBMITTED
            )
            if event.status != expected:
                raise ValidationError("This action is not allowed from the current state.")
        if len(reason) > 2000:
            raise ValidationError("Reason must be at most 2000 characters.")
        reason_required = target in (
            EventStatus.NEEDS_REVISION, EventStatus.REJECTED, EventStatus.CANCELLED
        )
        if reason_required and not reason:
            raise ValidationError("A reason is required for this transition.")
        if target in (EventStatus.SUBMITTED, EventStatus.PUBLISHED) or action == "approve":
            self._validate_ready(event, owner)
        now = timezone.now()
        if action == "unpublish" and now >= event.start_datetime:
            raise ValidationError("Unpublish is only available before the event starts.")
        if target == EventStatus.COMPLETED and now < event.end_datetime:
            raise ValidationError("Complete the event only after its end time.")
        if target == EventStatus.CANCELLED and now >= event.end_datetime:
            raise ValidationError("An event that has already ended cannot be cancelled.")

    # Abstraction: pemanggil cukup meminta transisi; validasi, locking, dan audit ditangani di sini.
    @transaction.atomic
    def transition(self, event_id, *, action, reason=""):
        actor, event, owner = self._lock_event(event_id)
        reason = reason.strip()
        self._validate_transition(actor, event, owner, action, reason)
        previous = event.status
        target = self.action_targets[action]
        event.status = target
        event.save(update_fields=["status", "updated_at"])
        EventTransition.objects.create(
            event=event, actor=actor, from_status=previous, to_status=target, reason=reason
        )
        return event

    @transaction.atomic
    def delete_draft(self, event_id):
        actor, event, _ = self._lock_event(event_id)
        self._require(actor, "events.delete_event")
        if event.status != EventStatus.DRAFT:
            raise ValidationError("Only an unsubmitted draft can be deleted.")
        name, storage = event.banner.name, event.banner.storage
        event.delete()
        if name:
            transaction.on_commit(lambda: storage.delete(name), robust=True)
