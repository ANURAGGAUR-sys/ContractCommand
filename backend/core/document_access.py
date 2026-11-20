from django.db.models import Q

from .permissions import has_role


DOCUMENT_RELATIONS = (
    'contract',
    'quotation_request',
    'vendor_quote',
    'purchase_order',
    'invoice',
    'delivery',
)


def document_queryset_for(user, queryset):
    if user.is_staff or user.is_superuser or has_role(user, 'Contracts Manager'):
        return queryset

    allowed = Q(pk__in=[])
    if has_role(user, 'Safety Officer') or has_role(user, 'Procurement Officer'):
        return queryset
    if has_role(user, 'Finance Officer') or has_role(user, 'Approver'):
        allowed |= (
            Q(contract__isnull=False)
            | Q(invoice__isnull=False)
            | Q(purchase_order__isnull=False)
        )
    if has_role(user, 'Requester'):
        allowed |= Q(contract__isnull=False)
        allowed |= Q(
            purchase_order__requisition__requested_by=user,
        )
    if has_role(user, 'Vendor'):
        allowed |= (
            Q(quotation_request__invited_vendors__user=user)
            | Q(vendor_quote__vendor__user=user)
            | Q(purchase_order__vendor__user=user)
            | Q(invoice__vendor__user=user)
            | Q(delivery__purchase_order__vendor__user=user)
        )
    return queryset.filter(allowed).distinct()


def can_upload_document(user, document_type, related_object, relation_name):
    if user.is_staff or user.is_superuser or has_role(user, 'Contracts Manager'):
        return True

    if has_role(user, 'Procurement Officer') and document_type in {
        'QUOTATION',
        'PURCHASE_ORDER',
        'DELIVERY_RECEIPT',
    }:
        return True
    if has_role(user, 'Finance Officer') and document_type == 'INVOICE':
        return True
    if has_role(user, 'Vendor'):
        if relation_name == 'vendor_quote':
            return related_object.vendor.user_id == user.id
        if relation_name == 'invoice':
            return related_object.vendor.user_id == user.id
    return False


def document_target(attrs, instance=None):
    values = {}
    for relation in DOCUMENT_RELATIONS:
        value = attrs.get(
            relation,
            getattr(instance, relation, None) if instance else None,
        )
        if value is not None:
            values[relation] = value
    return values
