from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    ApprovalViewSet,
    AuditLogViewSet,
    ContractViewSet,
    DeliveryViewSet,
    DocumentViewSet,
    InvoiceViewSet,
    NotificationViewSet,
    PaymentSessionViewSet,
    PurchaseOrderViewSet,
    QuotationRequestViewSet,
    ReportViewSet,
    RequisitionViewSet,
    VendorQuoteViewSet,
    VendorViewSet,
)

router = DefaultRouter()
router.register('contracts', ContractViewSet)
router.register('requisitions', RequisitionViewSet)
router.register('vendors', VendorViewSet)
router.register('invoices', InvoiceViewSet)
router.register('quotation-requests', QuotationRequestViewSet)
router.register('vendor-quotes', VendorQuoteViewSet)
router.register('purchase-orders', PurchaseOrderViewSet)
router.register('approvals', ApprovalViewSet)
router.register('deliveries', DeliveryViewSet)
router.register('payment-sessions', PaymentSessionViewSet)
router.register('documents', DocumentViewSet, basename='document')
router.register('notifications', NotificationViewSet)
router.register('audit-logs', AuditLogViewSet, basename='auditlog')
router.register('reports', ReportViewSet, basename='report')

urlpatterns = [path('', include(router.urls))]
