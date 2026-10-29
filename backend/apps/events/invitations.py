"""Pengiriman email undangan yang sudah tersimpan di database."""

import logging
from smtplib import SMTPException
from urllib.parse import urljoin

from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone


logger = logging.getLogger(__name__)
MAIL_ERRORS = (SMTPException, OSError, ImproperlyConfigured, ValueError)


def send_invitation_emails(invitations, *, site_url):
    """Kirim terpisah per penerima; kegagalan SMTP tidak menghapus undangan."""
    sent = []
    try:
        # OOP — Context-manager protocol: with memakai __enter__/__exit__ objek untuk mengelola konteks dan cleanup, termasuk saat terjadi exception.
        with get_connection() as connection:
            for invitation in invitations:
                acceptance_url = urljoin(
                    site_url,
                    reverse("eo_invitation_accept", args=[invitation.token]),
                )
                body = render_to_string("emails/committee_invitation.txt", {
                    "invitation": invitation,
                    "organizer_name": (
                        invitation.organizer.get_full_name().strip()
                        or invitation.organizer.email
                    ),
                    "acceptance_url": acceptance_url,
                    "expires_at": timezone.localtime(invitation.expires_at),
                    "event_names": (
                        [] if invitation.access_all
                        else list(invitation.events.values_list("title", flat=True))
                    ),
                })
                try:
                    delivered = EmailMessage(
                        subject="Undangan bergabung sebagai panitia SIMEVENT",
                        body=body,
                        to=[invitation.email],
                        connection=connection,
                    ).send(fail_silently=False)
                except MAIL_ERRORS:
                    logger.warning("Email undangan %s gagal dikirim.", invitation.pk)
                    continue
                if delivered:
                    invitation.email_sent_at = timezone.now()
                    invitation.save(update_fields=("email_sent_at",))
                    sent.append(invitation.email)
    except MAIL_ERRORS:
        logger.warning("Koneksi pengiriman email undangan gagal.")
    return {
        "sent": sent,
        "failed": [item.email for item in invitations if item.email not in sent],
    }
