# Fungsi file: Ekspresi agregasi ORM dan perhitungan persentase untuk statistik partisipasi event.

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count, Q

from apps.events.models import EventStatus

from .models import Attendance, RATING_FIELDS, RegistrationStatus


def participation_metrics(prefix=""):
    """Aggregate only Registration and its one-to-one attendance/feedback joins."""
    event_status = "status" if prefix else "event__status"
    active = Q(**{f"{prefix}status": RegistrationStatus.REGISTERED})
    eligible = active & Q(**{
        f"{event_status}__in": (EventStatus.PUBLISHED, EventStatus.COMPLETED),
    })
    present = Q(**{f"{prefix}attendance__status": Attendance.Status.PRESENT})
    valid_feedback = active & present & Q(**{event_status: EventStatus.COMPLETED})
    return {
        "total_registrations": Count(f"{prefix}pk"),
        "active_registrations": Count(f"{prefix}pk", filter=active),
        "cancelled_registrations": Count(
            f"{prefix}pk", filter=Q(**{f"{prefix}status": RegistrationStatus.CANCELLED}),
        ),
        "unique_participants": Count(f"{prefix}participant_id", distinct=True),
        "eligible_registrations": Count(f"{prefix}pk", filter=eligible),
        "total_attendance": Count(f"{prefix}attendance", filter=eligible & present),
        "recorded_check_ins": Count(f"{prefix}attendance"),
        "voided_check_ins": Count(
            f"{prefix}attendance",
            filter=Q(**{f"{prefix}attendance__status": Attendance.Status.VOIDED}),
        ),
        "feedback_count": Count(f"{prefix}feedback", filter=valid_feedback),
        **{
            f"average_{field}": Avg(f"{prefix}feedback__{field}", filter=valid_feedback)
            for field in RATING_FIELDS
        },
    }


def statistics_data(metrics):
    result = dict(metrics)
    denominator = result["eligible_registrations"]
    result["attendance_rate"] = (
        (Decimal(result["total_attendance"]) * 100 / denominator).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        if denominator else None
    )
    return result
