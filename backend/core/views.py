import csv
import io

from rest_framework import mixins, viewsets
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from .document_access import document_queryset_for
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
from .serializers import (
    ApprovalDecisionSerializer,
    ApprovalSerializer,
    AuditLogSerializer,
    ContractSerializer,
    DeliverySerializer,
    DocumentSerializer,
    InvoiceSerializer,
    NotificationSerializer,
    PaymentSessionSerializer,
    PurchaseOrderSerializer,
    QuotationRequestSerializer,
    RequisitionSerializer,
    VendorQuoteSerializer,
    VendorSerializer,
)
from .permissions import (
    IsAssignedApprover,
    has_role,
    requires_requester_scope,
    requires_vendor_scope,
)
from .reporting import report_filters, report_summary
from .services import create_notification, notify_roles, record_audit


class AuditedModelViewSet(viewsets.ModelViewSet):
    def field_snapshot(self, instance):
        return {
            field.attname: str(getattr(instance, field.attname))
            for field in instance._meta.concrete_fields
            if field.attname not in {'id', 'created_at', 'updated_at', 'file'}
        }

    def audit_created(self, instance):
        record_audit(self.request, 'CREATE', instance)

    def audit_updated(self, instance, before, action='UPDATE'):
        after = self.field_snapshot(instance)
        changes = {
            field_name: {'from': value, 'to': after.get(field_name)}
            for field_name, value in before.items()
            if value != after.get(field_name)
        }
        if changes:
            record_audit(self.request, action, instance, changes)

    def perform_create(self, serializer):
        self.audit_created(serializer.save())

    def perform_update(self, serializer):
        before = self.field_snapshot(serializer.instance)
        self.audit_updated(serializer.save(), before)

    def perform_destroy(self, instance):
        record_audit(self.request, 'DELETE', instance)
        super().perform_destroy(instance)


class ContractViewSet(AuditedModelViewSet):
    queryset = Contract.objects.select_related('owner').all()
    serializer_class = ContractSerializer
    filter_backends = [SearchFilter]
    search_fields = ['contract_number', 'title', 'status']

    def perform_create(self, serializer):
        self.audit_created(serializer.save(owner=self.request.user))


class RequisitionViewSet(AuditedModelViewSet):
    queryset = Requisition.objects.select_related('requested_by', 'contract').all()
    serializer_class = RequisitionSerializer
    filter_backends = [SearchFilter]
    search_fields = ['requisition_number', 'title', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_requester_scope(self.request.user):
            queryset = queryset.filter(requested_by=self.request.user)
        return queryset

    def perform_create(self, serializer):
        self.audit_created(serializer.save(requested_by=self.request.user))

    def perform_update(self, serializer):
        instance = serializer.instance
        previous_status = instance.status
        before = self.field_snapshot(instance)
        instance = serializer.save()
        if previous_status != instance.status and instance.status in ('APPROVED', 'REJECTED'):
            action_name = 'APPROVE' if instance.status == 'APPROVED' else 'REJECT'
            create_notification(
                instance.requested_by,
                'REQUISITION_DECISION',
                f'Requisition {instance.requisition_number} was {instance.status.lower()}.',
                related_object=instance,
            )
            self.audit_updated(instance, before, action=action_name)
        else:
            self.audit_updated(instance, before)


class VendorViewSet(AuditedModelViewSet):
    queryset = Vendor.objects.select_related('user').all()
    serializer_class = VendorSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'registration_number']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_vendor_scope(self.request.user):
            queryset = queryset.filter(user=self.request.user)
        return queryset


class InvoiceViewSet(AuditedModelViewSet):
    queryset = Invoice.objects.select_related('vendor', 'contract').all()
    serializer_class = InvoiceSerializer
    filter_backends = [SearchFilter]
    search_fields = ['invoice_number', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_vendor_scope(self.request.user):
            queryset = queryset.filter(vendor__user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        invoice = serializer.save()
        self.audit_created(invoice)
        notify_roles(
            ('Finance Officer',),
            'INVOICE_SUBMITTED',
            f'Invoice {invoice.invoice_number} was submitted for processing.',
            related_object=invoice,
        )

    def perform_update(self, serializer):
        invoice = serializer.instance
        previous_status = invoice.status
        before = self.field_snapshot(invoice)
        invoice = serializer.save()
        self.audit_updated(invoice, before)
        if previous_status != invoice.status and invoice.status in ('PAID', 'DISPUTED'):
            if invoice.vendor.user_id:
                create_notification(
                    invoice.vendor.user,
                    'PAYMENT_UPDATE',
                    f'Invoice {invoice.invoice_number} status is now {invoice.status.lower()}.',
                    related_object=invoice,
                )


class QuotationRequestViewSet(AuditedModelViewSet):
    queryset = QuotationRequest.objects.select_related(
        'requisition',
        'created_by',
    ).prefetch_related('invited_vendors')
    serializer_class = QuotationRequestSerializer
    filter_backends = [SearchFilter]
    search_fields = ['request_number', 'title', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_vendor_scope(self.request.user):
            queryset = queryset.filter(
                invited_vendors__user=self.request.user,
            ).distinct()
        return queryset

    def perform_create(self, serializer):
        self.audit_created(serializer.save(created_by=self.request.user))


class VendorQuoteViewSet(AuditedModelViewSet):
    queryset = VendorQuote.objects.select_related(
        'quotation_request',
        'vendor',
    )
    serializer_class = VendorQuoteSerializer
    filter_backends = [SearchFilter]
    search_fields = ['quotation_request__request_number', 'vendor__name', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_vendor_scope(self.request.user):
            queryset = queryset.filter(vendor__user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        vendor = Vendor.objects.filter(user=self.request.user).first()
        if vendor is None:
            raise PermissionDenied('This vendor account is not linked to a vendor profile.')
        self.audit_created(serializer.save(vendor=vendor))


class PurchaseOrderViewSet(AuditedModelViewSet):
    queryset = PurchaseOrder.objects.select_related(
        'requisition',
        'vendor',
        'quote',
        'contract',
        'created_by',
    )
    serializer_class = PurchaseOrderSerializer
    filter_backends = [SearchFilter]
    search_fields = ['po_number', 'status', 'vendor__name']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_vendor_scope(self.request.user):
            queryset = queryset.filter(vendor__user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        self.audit_created(serializer.save(created_by=self.request.user))

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        with transaction.atomic():
            purchase_order = self.get_object()
            if purchase_order.status != 'DRAFT':
                return Response(
                    {'detail': 'Only draft purchase orders can be submitted.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not purchase_order.vendor.approved:
                return Response(
                    {'detail': 'The purchase-order vendor must be approved.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            approvers = get_user_model().objects.filter(
                is_active=True,
                groups__name='Approver',
            ).distinct()
            if not approvers.exists():
                return Response(
                    {'detail': 'No active approver accounts are configured.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for approver in approvers:
                approval, created = Approval.objects.get_or_create(
                    purchase_order=purchase_order,
                    approver=approver,
                )
                if created:
                    create_notification(
                        approver,
                        'PENDING_APPROVAL',
                        f'Purchase order {purchase_order.po_number} requires your approval.',
                        related_object=approval,
                    )
            purchase_order.status = 'PENDING_APPROVAL'
            purchase_order.save(update_fields=['status', 'updated_at'])
            record_audit(
                request,
                'SUBMIT',
                purchase_order,
                {'status': {'from': 'DRAFT', 'to': 'PENDING_APPROVAL'}},
            )
            if purchase_order.quote_id:
                purchase_order.quote.status = 'SELECTED'
                purchase_order.quote.save(update_fields=['status'])
        return Response(self.get_serializer(purchase_order).data)


class ApprovalViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Approval.objects.select_related(
        'purchase_order',
        'approver',
    )
    serializer_class = ApprovalSerializer
    filter_backends = [SearchFilter]
    search_fields = ['purchase_order__po_number', 'status', 'approver__username']

    def get_permissions(self):
        if self.action == 'decide':
            return [IsAssignedApprover()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        if has_role(self.request.user, 'Approver') and not (
            has_role(self.request.user, 'Contracts Manager')
            or has_role(self.request.user, 'Procurement Officer')
        ):
            queryset = queryset.filter(approver=self.request.user)
        return queryset

    @action(detail=True, methods=['post'])
    def decide(self, request, pk=None):
        serializer = ApprovalDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            approval = self.get_object()
            if approval.status != 'PENDING':
                return Response(
                    {'detail': 'This approval has already been decided.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            now = timezone.now()
            approval.status = serializer.validated_data['decision']
            approval.comments = serializer.validated_data.get('comments', '')
            approval.decided_at = now
            approval.save(update_fields=['status', 'comments', 'decided_at'])
            action_name = 'APPROVE' if approval.status == 'APPROVED' else 'REJECT'
            record_audit(
                request,
                action_name,
                approval,
                {'status': {'from': 'PENDING', 'to': approval.status}},
            )

            purchase_order = PurchaseOrder.objects.select_for_update().get(
                pk=approval.purchase_order_id
            )
            if approval.status == 'REJECTED':
                purchase_order.status = 'REJECTED'
                Approval.objects.filter(
                    purchase_order=purchase_order,
                    status='PENDING',
                ).exclude(pk=approval.pk).update(status='CANCELLED', decided_at=now)
            elif not purchase_order.approvals.exclude(status='APPROVED').exists():
                purchase_order.status = 'APPROVED'
            if purchase_order.status in ('APPROVED', 'REJECTED'):
                purchase_order.save(update_fields=['status', 'updated_at'])
                create_notification(
                    purchase_order.created_by,
                    'APPROVAL_DECISION',
                    f'Purchase order {purchase_order.po_number} was {purchase_order.status.lower()}.',
                    related_object=purchase_order,
                )
        return Response(ApprovalSerializer(approval).data)


class DeliveryViewSet(AuditedModelViewSet):
    queryset = Delivery.objects.select_related(
        'purchase_order',
        'purchase_order__vendor',
        'created_by',
    )
    serializer_class = DeliverySerializer
    filter_backends = [SearchFilter]
    search_fields = ['delivery_number', 'tracking_number', 'status']

    def get_queryset(self):
        queryset = super().get_queryset()
        if requires_vendor_scope(self.request.user):
            queryset = queryset.filter(
                purchase_order__vendor__user=self.request.user,
            )
        return queryset

    def perform_create(self, serializer):
        self.audit_created(serializer.save(created_by=self.request.user))


class PaymentSessionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = PaymentSession.objects.select_related(
        'invoice',
        'created_by',
    )
    serializer_class = PaymentSessionSerializer
    filter_backends = [SearchFilter]
    search_fields = ['session_id', 'invoice__invoice_number', 'status']

    def perform_create(self, serializer):
        payment_session = serializer.save(created_by=self.request.user)
        record_audit(
            self.request,
            'PAYMENT',
            payment_session,
            {
                'status': {'to': 'PENDING'},
                'amount': str(payment_session.amount),
                'expires_at': payment_session.expires_at.isoformat(),
            },
        )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        with transaction.atomic():
            payment_session = PaymentSession.objects.select_for_update().select_related(
                'invoice',
            ).get(pk=self.get_object().pk)
            if payment_session.status != 'PENDING':
                return Response(
                    {'detail': 'This payment session is no longer pending.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            now = timezone.now()
            if payment_session.expires_at <= now:
                payment_session.status = 'EXPIRED'
                payment_session.save(update_fields=['status'])
                record_audit(
                    request,
                    'PAYMENT',
                    payment_session,
                    {'status': {'from': 'PENDING', 'to': 'EXPIRED'}},
                )
                return Response(
                    {'detail': 'This demo payment session has expired.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            invoice = Invoice.objects.select_for_update().get(
                pk=payment_session.invoice_id,
            )
            if (
                invoice.status != 'APPROVED'
                or invoice.amount != payment_session.amount
            ):
                payment_session.status = 'CANCELLED'
                payment_session.save(update_fields=['status'])
                record_audit(
                    request,
                    'PAYMENT',
                    payment_session,
                    {'status': {'from': 'PENDING', 'to': 'CANCELLED'}},
                )
                return Response(
                    {'detail': 'The invoice is no longer eligible for payment.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            invoice.status = 'PAID'
            invoice.save(update_fields=['status'])
            payment_session.status = 'COMPLETED'
            payment_session.completed_at = now
            payment_session.save(update_fields=['status', 'completed_at'])
            record_audit(
                request,
                'PAYMENT',
                payment_session,
                {
                    'status': {'from': 'PENDING', 'to': 'COMPLETED'},
                    'completed_at': now.isoformat(),
                },
            )
            if invoice.vendor.user_id:
                create_notification(
                    invoice.vendor.user,
                    'PAYMENT_UPDATE',
                    f'Payment for invoice {invoice.invoice_number} is complete.',
                    related_object=payment_session,
                )
            notify_roles(
                ('Finance Officer',),
                'PAYMENT_UPDATE',
                f'Payment for invoice {invoice.invoice_number} is complete.',
                related_object=payment_session,
            )
        return Response(self.get_serializer(payment_session).data)


class DocumentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Document.objects.select_related(
        'contract',
        'quotation_request',
        'vendor_quote',
        'purchase_order',
        'invoice',
        'delivery',
        'uploaded_by',
    )
    serializer_class = DocumentSerializer
    filter_backends = [SearchFilter]
    search_fields = ['original_filename', 'document_type']

    def get_queryset(self):
        return document_queryset_for(self.request.user, super().get_queryset())

    def perform_create(self, serializer):
        document = serializer.save(uploaded_by=self.request.user)
        record_audit(
            self.request,
            'UPLOAD',
            document,
            {
                'document_type': document.document_type,
                'filename': document.original_filename,
                'size_bytes': document.size_bytes,
            },
        )

    def perform_destroy(self, instance):
        storage = instance.file.storage
        filename = instance.file.name
        record_audit(self.request, 'DELETE', instance)
        instance.delete()
        storage.delete(filename)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        document = self.get_object()
        record_audit(
            request,
            'READ',
            document,
            {'event': 'download'},
        )
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=document.original_filename,
            content_type=document.content_type,
        )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=True, methods=['patch'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response(self.get_serializer(notification).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related('user').all()
    serializer_class = AuditLogSerializer
    filter_backends = [SearchFilter]
    search_fields = ['entity_type', 'object_label', 'action', 'user__username']


class ReportViewSet(viewsets.GenericViewSet):
    queryset = AuditLog.objects.none()

    def list(self, request):
        start_date, end_date, status_filter = report_filters(request.query_params)
        return Response(report_summary(start_date, end_date, status_filter))

    @action(detail=False, methods=['get'])
    def summary(self, request):
        return self.list(request)

    @action(detail=False, methods=['get'])
    def export(self, request):
        report_type = request.query_params.get('report', 'summary')
        start_date, end_date, status_filter = report_filters(request.query_params)
        summary = report_summary(start_date, end_date, status_filter)
        report_sections = {
            'contracts': summary['contract_status'],
            'vendors': summary['vendor_performance'],
            'invoices': summary['invoice_status'],
            'payments': summary['payment_status'],
            'requisitions': summary['requisition_statistics'],
        }
        if report_type == 'expenditure':
            rows = [
                {'metric': name, 'amount': amount}
                for name, amount in summary['procurement_expenditure'].items()
            ]
        elif report_type in report_sections:
            rows = report_sections[report_type]
        elif report_type == 'summary':
            rows = []
            for name, items in report_sections.items():
                for item in items:
                    rows.append({'section': name, **item})
            rows.extend(
                {'section': 'expenditure', 'metric': name, 'amount': amount}
                for name, amount in summary['procurement_expenditure'].items()
            )
        else:
            return Response(
                {'report': 'Choose summary, expenditure, contracts, vendors, invoices, payments, or requisitions.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        columns = sorted({key for row in rows for key in row})
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns or ['message'])
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        else:
            writer.writerow({'message': 'No matching records'})
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="contractcommand-{report_type}.csv"'
        return response

# Create your views here.
