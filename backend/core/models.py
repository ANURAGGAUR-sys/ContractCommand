import uuid
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.deconstruct import deconstructible


def demo_payment_expiry():
    return timezone.now() + timedelta(minutes=10)


@deconstructible
class PrivateDocumentStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(
            location=settings.PRIVATE_DOCUMENT_ROOT,
            base_url=None,
        )

    def url(self, name):
        raise ValueError('Private documents do not have public URLs.')


class Contract(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('ACTIVE', 'Active'),
        ('PENDING', 'Pending'), ('CLOSED', 'Closed'),
    ]
    contract_number = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    start_date = models.DateField()
    end_date = models.DateField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.contract_number} - {self.title}"


class Requisition(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'), ('REJECTED', 'Rejected'),
    ]
    requisition_number = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)
    justification = models.TextField()
    estimated_value = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    contract = models.ForeignKey(Contract, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class Vendor(models.Model):
    name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, unique=True)
    contact_email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    compliance_score = models.PositiveSmallIntegerField(default=0)
    approved = models.BooleanField(default=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='vendor_profile',
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'), ('APPROVED', 'Approved'),
        ('PAID', 'Paid'), ('DISPUTED', 'Disputed'),
    ]
    invoice_number = models.CharField(max_length=30, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    invoice_date = models.DateField()
    due_date = models.DateField()
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices',
    )


class QuotationRequest(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    request_number = models.CharField(max_length=30, unique=True)
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.PROTECT,
        related_name='quotation_requests',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    close_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    invited_vendors = models.ManyToManyField(Vendor, related_name='quotation_requests')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_quotation_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.request_number} - {self.title}'


class VendorQuote(models.Model):
    STATUS_CHOICES = [
        ('SUBMITTED', 'Submitted'),
        ('SELECTED', 'Selected'),
        ('REJECTED', 'Rejected'),
        ('WITHDRAWN', 'Withdrawn'),
    ]
    quotation_request = models.ForeignKey(
        QuotationRequest,
        on_delete=models.PROTECT,
        related_name='quotes',
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='quotes')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    proposal = models.TextField(blank=True)
    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUBMITTED')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('quotation_request', 'vendor'),
                name='unique_vendor_quote_per_request',
            ),
        ]


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING_APPROVAL', 'Pending approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('ISSUED', 'Issued'),
        ('CLOSED', 'Closed'),
        ('CANCELLED', 'Cancelled'),
    ]
    po_number = models.CharField(max_length=30, unique=True)
    requisition = models.ForeignKey(
        Requisition,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
    )
    quote = models.ForeignKey(
        VendorQuote,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='purchase_orders',
    )
    contract = models.ForeignKey(
        Contract,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='purchase_orders',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    expected_delivery_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_purchase_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.po_number


class Approval(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='approvals',
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='purchase_order_approvals',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    comments = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('purchase_order', 'approver'),
                name='unique_purchase_order_approver',
            ),
        ]


class Delivery(models.Model):
    STATUS_CHOICES = [
        ('EXPECTED', 'Expected'),
        ('PARTIAL', 'Partial'),
        ('DELIVERED', 'Delivered'),
        ('REJECTED', 'Rejected'),
    ]
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name='deliveries',
    )
    delivery_number = models.CharField(max_length=30, unique=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='EXPECTED')
    expected_date = models.DateField(null=True, blank=True)
    delivered_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_deliveries',
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PaymentSession(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('EXPIRED', 'Expired'),
        ('CANCELLED', 'Cancelled'),
    ]
    session_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payment_sessions',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    expires_at = models.DateTimeField(default=demo_payment_expiry)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_payment_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.session_id)


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('CONTRACT', 'Contract'),
        ('QUOTATION', 'Quotation'),
        ('PURCHASE_ORDER', 'Purchase order'),
        ('INVOICE', 'Invoice'),
        ('DELIVERY_RECEIPT', 'Delivery receipt'),
    ]
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    file = models.FileField(
        upload_to='contractcommand-documents/%Y/%m/',
        storage=PrivateDocumentStorage(),
    )
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    contract = models.ForeignKey(
        Contract,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    quotation_request = models.ForeignKey(
        QuotationRequest,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    vendor_quote = models.ForeignKey(
        VendorQuote,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    invoice = models.ForeignKey(
        Invoice,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    delivery = models.ForeignKey(
        Delivery,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_filename


class Notification(models.Model):
    TYPE_CHOICES = [
        ('REQUISITION_DECISION', 'Requisition decision'),
        ('INVOICE_SUBMITTED', 'Invoice submitted'),
        ('PAYMENT_UPDATE', 'Payment update'),
        ('CONTRACT_EXPIRING', 'Contract expiring'),
        ('PENDING_APPROVAL', 'Pending approval'),
        ('APPROVAL_DECISION', 'Approval decision'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    message = models.CharField(max_length=500)
    related_type = models.CharField(max_length=50, blank=True)
    related_id = models.CharField(max_length=50, blank=True)
    dedupe_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'dedupe_key'),
                name='unique_user_notification_dedupe_key',
            ),
        ]


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('SUBMIT', 'Submit'),
        ('PAYMENT', 'Payment'),
        ('UPLOAD', 'Upload'),
        ('READ', 'Read'),
        ('DELETE', 'Delete'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=80)
    object_id = models.CharField(max_length=80)
    object_label = models.CharField(max_length=255)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Audit records are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit records are immutable.')

# Create your models here.
