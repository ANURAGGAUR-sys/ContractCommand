import os
import zipfile

from django.utils import timezone
from rest_framework import serializers
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
from .document_access import document_target, can_upload_document
from .permissions import has_role


MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_DOCUMENT_TYPES = {
    '.pdf': ('application/pdf', None),
    '.docx': (
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'word/document.xml',
    ),
    '.xlsx': (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'xl/workbook.xml',
    ),
    '.png': ('image/png', None),
    '.jpg': ('image/jpeg', None),
    '.jpeg': ('image/jpeg', None),
    '.txt': ('text/plain', None),
}


def validate_document_file(upload):
    extension = os.path.splitext(upload.name)[1].lower()
    file_type = ALLOWED_DOCUMENT_TYPES.get(extension)
    if file_type is None:
        raise serializers.ValidationError(
            'Allowed file types are PDF, DOCX, XLSX, PNG, JPG, and TXT.'
        )
    expected_type, zip_member = file_type
    if upload.size > MAX_DOCUMENT_SIZE:
        raise serializers.ValidationError('Maximum document size is 10 MB.')
    if upload.content_type != expected_type:
        raise serializers.ValidationError(
            'The uploaded file type does not match its filename.'
        )

    upload.seek(0)
    header = upload.read(8)
    upload.seek(0)
    if extension == '.pdf' and not header.startswith(b'%PDF-'):
        raise serializers.ValidationError('The file is not a valid PDF document.')
    if extension == '.png' and header != b'\x89PNG\r\n\x1a\n':
        raise serializers.ValidationError('The file is not a valid PNG image.')
    if extension in ('.jpg', '.jpeg') and not header.startswith(b'\xff\xd8\xff'):
        raise serializers.ValidationError('The file is not a valid JPEG image.')
    if zip_member:
        try:
            with zipfile.ZipFile(upload) as archive:
                if zip_member not in archive.namelist():
                    raise serializers.ValidationError(
                        'The file is not a valid Office document.'
                    )
        except (OSError, zipfile.BadZipFile):
            raise serializers.ValidationError(
                'The file is not a valid Office document.'
            ) from None
        finally:
            upload.seek(0)
    if extension == '.txt':
        content = upload.read()
        try:
            content.decode('utf-8')
        except UnicodeDecodeError:
            raise serializers.ValidationError('Text files must contain UTF-8 text.') from None
        finally:
            upload.seek(0)
        if b'\x00' in content:
            raise serializers.ValidationError('Text files cannot contain NUL bytes.')


class ContractSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Contract
        fields = '__all__'
        read_only_fields = ('owner', 'owner_username', 'created_at', 'updated_at')

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })
        return attrs

    def validate_value(self, value):
        if value <= 0:
            raise serializers.ValidationError('Contract value must be greater than zero.')
        return value


class RequisitionSerializer(serializers.ModelSerializer):
    requested_by_username = serializers.CharField(
        source='requested_by.username',
        read_only=True,
    )

    class Meta:
        model = Requisition
        fields = '__all__'
        read_only_fields = ('requested_by', 'requested_by_username', 'created_at')

    def validate_estimated_value(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Estimated value must be greater than zero.'
            )
        return value

    def validate(self, attrs):
        status = attrs.get('status', getattr(self.instance, 'status', 'DRAFT'))
        user = self.context['request'].user
        can_decide = (
            user.is_staff
            or user.is_superuser
            or user.groups.filter(name='Contracts Manager').exists()
        )
        if status in ('APPROVED', 'REJECTED') and not can_decide:
            raise serializers.ValidationError({
                'status': 'Only a Contracts Manager or administrator can approve or reject requisitions.'
            })
        return attrs


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'
        read_only_fields = ('created_at', 'user')

    def validate_compliance_score(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                'Compliance score must be between 0 and 100.'
            )
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    contract_number = serializers.CharField(
        source='contract.contract_number',
        read_only=True,
    )

    class Meta:
        model = Invoice
        fields = '__all__'

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Invoice amount must be greater than zero.')
        return value

    def validate(self, attrs):
        invoice_date = attrs.get('invoice_date', getattr(self.instance, 'invoice_date', None))
        due_date = attrs.get('due_date', getattr(self.instance, 'due_date', None))
        purchase_order = attrs.get(
            'purchase_order',
            getattr(self.instance, 'purchase_order', None),
        )
        vendor = attrs.get('vendor', getattr(self.instance, 'vendor', None))
        contract = attrs.get('contract', getattr(self.instance, 'contract', None))
        if invoice_date and due_date and due_date < invoice_date:
            raise serializers.ValidationError({
                'due_date': 'Due date cannot be before invoice date.'
            })
        if purchase_order and vendor and purchase_order.vendor_id != vendor.id:
            raise serializers.ValidationError({
                'purchase_order': 'The invoice vendor must match the purchase order.'
            })
        if (
            purchase_order
            and contract
            and purchase_order.contract_id
            and purchase_order.contract_id != contract.id
        ):
            raise serializers.ValidationError({
                'purchase_order': 'The invoice contract must match the purchase order.'
            })
        return attrs


class QuotationRequestSerializer(serializers.ModelSerializer):
    requisition_number = serializers.CharField(
        source='requisition.requisition_number',
        read_only=True,
    )

    class Meta:
        model = QuotationRequest
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at')

    def validate(self, attrs):
        requisition = attrs.get(
            'requisition',
            getattr(self.instance, 'requisition', None),
        )
        vendors = attrs.get('invited_vendors')
        if requisition and requisition.status != 'APPROVED':
            raise serializers.ValidationError({
                'requisition': 'Only approved requisitions can be sent for quotation.'
            })
        if vendors is not None and any(not vendor.approved for vendor in vendors):
            raise serializers.ValidationError({
                'invited_vendors': 'Only approved vendors can be invited.'
            })
        return attrs


class VendorQuoteSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    request_number = serializers.CharField(
        source='quotation_request.request_number',
        read_only=True,
    )

    class Meta:
        model = VendorQuote
        fields = '__all__'
        read_only_fields = ('vendor', 'status', 'submitted_at')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quote amount must be greater than zero.')
        return value

    def validate(self, attrs):
        quotation_request = attrs.get(
            'quotation_request',
            getattr(self.instance, 'quotation_request', None),
        )
        user = self.context['request'].user
        vendor = getattr(user, 'vendor_profile', None)
        if has_role(user, 'Vendor') and not (user.is_staff or user.is_superuser):
            if vendor is None:
                raise serializers.ValidationError(
                    'This vendor account is not linked to a vendor profile.'
                )
            if not vendor.approved:
                raise serializers.ValidationError(
                    'Only approved vendors can submit quotations.'
                )
            if quotation_request and not quotation_request.invited_vendors.filter(
                pk=vendor.pk
            ).exists():
                raise serializers.ValidationError(
                    'Your vendor is not invited to this quotation request.'
                )
            if quotation_request and quotation_request.status != 'OPEN':
                raise serializers.ValidationError(
                    'This quotation request is not open for submissions.'
                )
            if (
                quotation_request
                and quotation_request.close_date
                and quotation_request.close_date < timezone.localdate()
            ):
                raise serializers.ValidationError(
                    'The quotation request submission deadline has passed.'
                )
        return attrs


class PurchaseOrderSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    requisition_number = serializers.CharField(
        source='requisition.requisition_number',
        read_only=True,
    )

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at', 'updated_at', 'status')

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Purchase order amount must be greater than zero.'
            )
        return value

    def validate(self, attrs):
        quote = attrs.get('quote', getattr(self.instance, 'quote', None))
        vendor = attrs.get('vendor', getattr(self.instance, 'vendor', None))
        requisition = attrs.get(
            'requisition',
            getattr(self.instance, 'requisition', None),
        )
        if quote and vendor and quote.vendor_id != vendor.id:
            raise serializers.ValidationError({
                'quote': 'The selected quote must belong to the purchase-order vendor.'
            })
        if quote and requisition and quote.quotation_request.requisition_id != requisition.id:
            raise serializers.ValidationError({
                'quote': 'The selected quote must belong to the purchase-order requisition.'
            })
        if requisition and requisition.status != 'APPROVED':
            raise serializers.ValidationError({
                'requisition': 'Purchase orders require an approved requisition.'
            })
        if vendor and not vendor.approved:
            raise serializers.ValidationError({
                'vendor': 'Purchase orders require an approved vendor.'
            })
        return attrs


class ApprovalSerializer(serializers.ModelSerializer):
    approver_username = serializers.CharField(
        source='approver.username',
        read_only=True,
    )
    po_number = serializers.CharField(
        source='purchase_order.po_number',
        read_only=True,
    )

    class Meta:
        model = Approval
        fields = '__all__'
        read_only_fields = (
            'purchase_order',
            'approver',
            'status',
            'comments',
            'decided_at',
            'created_at',
        )


class ApprovalDecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=('APPROVED', 'REJECTED'))
    comments = serializers.CharField(required=False, allow_blank=True)


class DeliverySerializer(serializers.ModelSerializer):
    po_number = serializers.CharField(
        source='purchase_order.po_number',
        read_only=True,
    )
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True,
    )

    class Meta:
        model = Delivery
        fields = '__all__'
        read_only_fields = ('created_by', 'created_at')

    def validate(self, attrs):
        status_value = attrs.get('status', getattr(self.instance, 'status', 'EXPECTED'))
        delivered_date = attrs.get(
            'delivered_date',
            getattr(self.instance, 'delivered_date', None),
        )
        if status_value == 'DELIVERED' and not delivered_date:
            raise serializers.ValidationError({
                'delivered_date': 'A delivered date is required for completed deliveries.'
            })
        return attrs


class PaymentSessionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    status = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True,
    )

    class Meta:
        model = PaymentSession
        fields = '__all__'
        read_only_fields = (
            'session_id',
            'amount',
            'status',
            'expires_at',
            'completed_at',
            'created_by',
            'created_at',
        )

    def validate_invoice(self, invoice):
        if invoice.status != 'APPROVED':
            raise serializers.ValidationError(
                'Only approved invoices can start a demo payment session.'
            )
        return invoice

    def get_status(self, payment_session):
        if (
            payment_session.status == 'PENDING'
            and payment_session.expires_at <= timezone.now()
        ):
            return 'EXPIRED'
        return payment_session.status

    def create(self, validated_data):
        invoice = validated_data['invoice']
        return PaymentSession.objects.create(
            **validated_data,
            amount=invoice.amount,
        )


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    uploaded_by_username = serializers.CharField(
        source='uploaded_by.username',
        read_only=True,
    )

    class Meta:
        model = Document
        fields = (
            'id',
            'document_type',
            'file',
            'original_filename',
            'content_type',
            'size_bytes',
            'contract',
            'quotation_request',
            'vendor_quote',
            'purchase_order',
            'invoice',
            'delivery',
            'uploaded_by',
            'uploaded_by_username',
            'created_at',
        )
        read_only_fields = (
            'original_filename',
            'content_type',
            'size_bytes',
            'uploaded_by',
            'uploaded_by_username',
            'created_at',
        )

    def validate_file(self, upload):
        validate_document_file(upload)
        if len(os.path.basename(upload.name.replace('\\', '/'))) > 255:
            raise serializers.ValidationError('Filename cannot exceed 255 characters.')
        return upload

    def validate(self, attrs):
        targets = document_target(attrs, self.instance)
        if len(targets) != 1:
            raise serializers.ValidationError(
                'Attach a document to exactly one supported record.'
            )
        document_type = attrs.get(
            'document_type',
            getattr(self.instance, 'document_type', None),
        )
        relation_name, related_object = next(iter(targets.items()))
        required_relation = {
            'CONTRACT': ('contract',),
            'QUOTATION': ('quotation_request', 'vendor_quote'),
            'PURCHASE_ORDER': ('purchase_order',),
            'INVOICE': ('invoice',),
            'DELIVERY_RECEIPT': ('delivery',),
        }.get(document_type, ())
        if relation_name not in required_relation:
            raise serializers.ValidationError({
                'document_type': 'Document type does not match the linked record.'
            })
        request = self.context.get('request')
        if request and not can_upload_document(
            request.user,
            document_type,
            related_object,
            relation_name,
        ):
            raise serializers.ValidationError(
                'You are not allowed to attach documents to this record.'
            )
        return attrs

    def create(self, validated_data):
        upload = validated_data['file']
        validated_data['original_filename'] = os.path.basename(
            upload.name.replace('\\', '/')
        )
        validated_data['content_type'] = upload.content_type
        validated_data['size_bytes'] = upload.size
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = (
            'user',
            'notification_type',
            'message',
            'related_type',
            'related_id',
            'dedupe_key',
            'created_at',
            'read_at',
        )


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'
        read_only_fields = (
            'user',
            'action',
            'entity_type',
            'object_id',
            'object_label',
            'changes',
            'ip_address',
            'created_at',
            'username',
        )
