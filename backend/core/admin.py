from django.contrib import admin
from .models import (
    Approval,
    AuditLog,
    Contract,
    Delivery,
    Document,
    Invoice,
    Notification,
    PaymentSession,
    PurchaseOrder,
    QuotationRequest,
    Requisition,
    Vendor,
    VendorQuote,
)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'title', 'status', 'value', 'owner')
    search_fields = ('contract_number', 'title')
    list_filter = ('status',)


@admin.register(Requisition)
class RequisitionAdmin(admin.ModelAdmin):
    list_display = ('requisition_number', 'title', 'status', 'estimated_value')
    search_fields = ('requisition_number', 'title')
    list_filter = ('status',)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'user', 'approved', 'compliance_score')
    search_fields = ('name', 'registration_number')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'vendor', 'contract', 'amount', 'status')


@admin.register(QuotationRequest)
class QuotationRequestAdmin(admin.ModelAdmin):
    list_display = ('request_number', 'title', 'requisition', 'status', 'close_date')
    search_fields = ('request_number', 'title')
    list_filter = ('status',)
    filter_horizontal = ('invited_vendors',)


@admin.register(VendorQuote)
class VendorQuoteAdmin(admin.ModelAdmin):
    list_display = ('quotation_request', 'vendor', 'amount', 'status', 'submitted_at')
    search_fields = ('quotation_request__request_number', 'vendor__name')
    list_filter = ('status',)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'vendor', 'requisition', 'amount', 'status')
    search_fields = ('po_number', 'vendor__name')
    list_filter = ('status',)


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'approver', 'status', 'decided_at')
    list_filter = ('status',)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('delivery_number', 'purchase_order', 'status', 'expected_date')
    search_fields = ('delivery_number', 'tracking_number', 'purchase_order__po_number')
    list_filter = ('status',)


@admin.register(PaymentSession)
class PaymentSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'invoice', 'amount', 'status', 'expires_at')
    search_fields = ('session_id', 'invoice__invoice_number')
    list_filter = ('status',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'original_filename',
        'document_type',
        'size_bytes',
        'uploaded_by',
        'created_at',
    )
    list_filter = ('document_type',)
    search_fields = ('original_filename',)
    readonly_fields = [
        field.name for field in Document._meta.fields if field.name != 'file'
    ]
    fields = readonly_fields

    def has_add_permission(self, request):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'created_at', 'read_at')
    list_filter = ('notification_type', 'read_at')
    search_fields = ('user__username', 'message')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'entity_type', 'object_label')
    list_filter = ('action', 'entity_type')
    search_fields = ('object_label', 'user__username')
    readonly_fields = [field.name for field in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
