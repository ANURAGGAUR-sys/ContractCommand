from django.contrib.auth import get_user_model

from .models import AuditLog, Notification


def create_notification(
    user,
    notification_type,
    message,
    related_object=None,
    dedupe_key=None,
):
    defaults = {
        'notification_type': notification_type,
        'message': message,
        'related_type': related_object._meta.label if related_object else '',
        'related_id': str(related_object.pk) if related_object else '',
    }
    if dedupe_key:
        notification, _ = Notification.objects.get_or_create(
            user=user,
            dedupe_key=dedupe_key,
            defaults=defaults,
        )
        return notification
    return Notification.objects.create(user=user, **defaults)


def notify_roles(roles, notification_type, message, related_object=None):
    users = get_user_model().objects.filter(
        is_active=True,
        groups__name__in=roles,
    ).distinct()
    return [
        create_notification(
            user,
            notification_type,
            message,
            related_object=related_object,
        )
        for user in users
    ]


def record_audit(request, action, instance, changes=None):
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        user = None
    remote_addr = request.META.get('REMOTE_ADDR') if request else None
    return AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=instance._meta.label,
        object_id=str(instance.pk),
        object_label=str(instance)[:255],
        changes=changes or {},
        ip_address=remote_addr,
    )
