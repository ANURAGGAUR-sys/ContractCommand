from rest_framework.permissions import BasePermission, SAFE_METHODS


APPLICATION_ROLES = (
    'Safety Officer',
    'Contracts Manager',
    'Procurement Officer',
    'Requester',
    'Approver',
    'Finance Officer',
    'Vendor',
)

ROLE_PERMISSIONS = {
    'Contracts Manager': {
        'contract': {'read', 'create', 'update'},
        'requisition': {'read', 'create', 'update'},
        'vendor': {'read', 'create', 'update'},
        'invoice': {'read', 'create', 'update'},
        'quotationrequest': {'read', 'create', 'update'},
        'vendorquote': {'read'},
        'purchaseorder': {'read', 'create', 'update'},
        'approval': {'read'},
        'delivery': {'read', 'create', 'update'},
        'document': {'read', 'create'},
        'notification': {'read', 'update'},
        'auditlog': {'read'},
        'report': {'read'},
    },
    'Safety Officer': {
        'contract': {'read'},
        'requisition': {'read', 'create', 'update'},
        'vendor': {'read', 'create', 'update'},
        'invoice': {'read'},
        'quotationrequest': {'read'},
        'vendorquote': {'read'},
        'purchaseorder': {'read'},
        'delivery': {'read'},
        'document': {'read'},
        'notification': {'read', 'update'},
    },
    'Procurement Officer': {
        'contract': {'read'},
        'requisition': {'read', 'create', 'update'},
        'vendor': {'read', 'create', 'update'},
        'invoice': {'read'},
        'quotationrequest': {'read', 'create', 'update'},
        'vendorquote': {'read'},
        'purchaseorder': {'read', 'create', 'update'},
        'approval': {'read'},
        'delivery': {'read', 'create', 'update'},
        'document': {'read', 'create'},
        'notification': {'read', 'update'},
        'report': {'read'},
    },
    'Requester': {
        'contract': {'read'},
        'requisition': {'read', 'create', 'update'},
        'document': {'read'},
        'notification': {'read', 'update'},
    },
    'Approver': {
        'contract': {'read'},
        'requisition': {'read'},
        'vendor': {'read'},
        'invoice': {'read'},
        'purchaseorder': {'read'},
        'approval': {'read'},
        'document': {'read'},
        'notification': {'read', 'update'},
    },
    'Finance Officer': {
        'contract': {'read'},
        'requisition': {'read'},
        'vendor': {'read'},
        'invoice': {'read', 'update'},
        'purchaseorder': {'read'},
        'approval': {'read'},
        'delivery': {'read'},
        'paymentsession': {'read', 'create'},
        'document': {'read', 'create'},
        'notification': {'read', 'update'},
        'auditlog': {'read'},
        'report': {'read'},
    },
    'Vendor': {
        'vendor': {'read'},
        'invoice': {'read'},
        'quotationrequest': {'read'},
        'vendorquote': {'read', 'create', 'update'},
        'purchaseorder': {'read'},
        'delivery': {'read'},
        'document': {'read', 'create'},
        'notification': {'read', 'update'},
    },
}

REQUISITION_REVIEW_ROLES = (
    'Contracts Manager',
    'Safety Officer',
    'Procurement Officer',
    'Approver',
    'Finance Officer',
)


def has_role(user, role):
    return user.groups.filter(name=role).exists()


def requires_vendor_scope(user):
    return has_role(user, 'Vendor') and not user.groups.filter(
        name__in=REQUISITION_REVIEW_ROLES
    ).exists()


def requires_requester_scope(user):
    return has_role(user, 'Requester') and not user.groups.filter(
        name__in=REQUISITION_REVIEW_ROLES
    ).exists()


class IsPlatformMember(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        action = {
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete',
        }.get(request.method)
        if request.method in SAFE_METHODS:
            action = 'read'
        if action is None:
            return False
        resource = getattr(view, 'basename', None)
        roles = user.groups.filter(name__in=APPLICATION_ROLES).values_list(
            'name',
            flat=True,
        )
        if resource is None:
            return bool(roles)
        return any(
            action in ROLE_PERMISSIONS.get(role, {}).get(resource, set())
            for role in roles
        )


class IsAssignedApprover(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_staff
                or user.is_superuser
                or has_role(user, 'Approver')
            )
        )

    def has_object_permission(self, request, view, obj):
        user = request.user
        return bool(
            user.is_staff
            or user.is_superuser
            or (has_role(user, 'Approver') and obj.approver_id == user.id)
        )
