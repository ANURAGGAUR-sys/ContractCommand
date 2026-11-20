from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .permissions import APPLICATION_ROLES, ROLE_PERMISSIONS


MODULES_BY_RESOURCE = {
    'contract': 'contracts',
    'requisition': 'requisitions',
    'vendor': 'vendors',
    'invoice': 'invoices',
    'quotationrequest': 'quotation-requests',
    'vendorquote': 'vendor-quotes',
    'purchaseorder': 'purchase-orders',
    'approval': 'approvals',
    'delivery': 'deliveries',
    'paymentsession': 'payment-sessions',
    'document': 'documents',
    'notification': 'notifications',
    'auditlog': 'audit-logs',
    'report': 'reports',
}


def user_payload(user):
    roles = list(
        user.groups.filter(name__in=APPLICATION_ROLES)
        .order_by('name')
        .values_list('name', flat=True)
    )
    capabilities = {}
    for resource, module in MODULES_BY_RESOURCE.items():
        actions = set()
        if user.is_staff or user.is_superuser:
            actions.update(('read', 'create', 'update', 'delete'))
        else:
            for role in roles:
                actions.update(ROLE_PERMISSIONS.get(role, {}).get(resource, set()))
        capabilities[module] = sorted(actions)
    return {
        'id': user.pk,
        'username': user.get_username(),
        'displayName': user.get_full_name() or user.get_username(),
        'roles': roles,
        'isStaff': user.is_staff or user.is_superuser,
        'capabilities': capabilities,
    }


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        has_application_role = user.groups.filter(name__in=APPLICATION_ROLES).exists()
        if not (user.is_staff or user.is_superuser or has_application_role):
            raise PermissionDenied('This account has no assigned application role.')
        data['user'] = user_payload(user)
        return data


class RoleTokenObtainPairView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = (AllowAny,)


class RoleTokenRefreshView(TokenRefreshView):
    permission_classes = (AllowAny,)


class RoleTokenBlacklistView(TokenBlacklistView):
    permission_classes = (AllowAny,)


@api_view(['GET'])
def current_user(request):
    return Response(user_payload(request.user))
