from django.db.models import Count, DateTimeField, Q, Sum
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from .models import (
    Contract,
    Delivery,
    Invoice,
    PaymentSession,
    PurchaseOrder,
    Requisition,
    Vendor,
    VendorQuote,
)


def report_filters(params):
    start_date = parse_date(params.get('date_from', '')) if params.get('date_from') else None
    end_date = parse_date(params.get('date_to', '')) if params.get('date_to') else None
    if params.get('date_from') and start_date is None:
        raise ValidationError({'date_from': 'Use YYYY-MM-DD format.'})
    if params.get('date_to') and end_date is None:
        raise ValidationError({'date_to': 'Use YYYY-MM-DD format.'})
    if start_date and end_date and end_date < start_date:
        raise ValidationError({'date_to': 'Must be on or after date_from.'})
    return start_date, end_date, params.get('status') or None


def filter_queryset(queryset, date_field, start_date, end_date, status):
    field = queryset.model._meta.get_field(date_field)
    date_lookup = f'{date_field}__date' if isinstance(field, DateTimeField) else date_field
    if start_date:
        queryset = queryset.filter(**{f'{date_lookup}__gte': start_date})
    if end_date:
        queryset = queryset.filter(**{f'{date_lookup}__lte': end_date})
    if status:
        queryset = queryset.filter(status__iexact=status)
    return queryset


def status_totals(queryset, amount_field=None):
    aggregates = {'count': Count('id')}
    if amount_field:
        aggregates['total_amount'] = Sum(amount_field)
    return list(
        queryset.values('status')
        .annotate(**aggregates)
        .order_by('status')
    )


def report_summary(start_date, end_date, status):
    contracts = filter_queryset(
        Contract.objects.all(), 'created_at', start_date, end_date, status
    )
    requisitions = filter_queryset(
        Requisition.objects.all(), 'created_at', start_date, end_date, status
    )
    orders = filter_queryset(
        PurchaseOrder.objects.select_related('vendor'),
        'created_at',
        start_date,
        end_date,
        status,
    )
    invoices = filter_queryset(
        Invoice.objects.select_related('vendor'),
        'invoice_date',
        start_date,
        end_date,
        status,
    )
    payments = filter_queryset(
        PaymentSession.objects.all(), 'created_at', start_date, end_date, status
    )
    quotes = filter_queryset(
        VendorQuote.objects.all(), 'submitted_at', start_date, end_date, status
    )
    deliveries = filter_queryset(
        Delivery.objects.select_related('purchase_order'),
        'created_at',
        start_date,
        end_date,
        status,
    )

    quote_totals = {
        row['vendor_id']: row
        for row in quotes.values('vendor_id').annotate(
            quote_count=Count('id'),
            selected_quote_count=Count('id', filter=Q(status='SELECTED')),
        )
    }
    order_totals = {
        row['vendor_id']: row
        for row in orders.values('vendor_id').annotate(
            purchase_order_count=Count('id'),
            purchase_order_total=Sum('amount'),
        )
    }
    delivery_totals = {
        row['purchase_order__vendor_id']: row['delivery_count']
        for row in deliveries.values('purchase_order__vendor_id').annotate(
            delivery_count=Count('id')
        )
    }
    vendor_ids = set(quote_totals) | set(order_totals) | set(delivery_totals)
    vendors = []
    for vendor in Vendor.objects.filter(pk__in=vendor_ids).order_by('name'):
        vendors.append({
            'vendor_id': vendor.pk,
            'vendor_name': vendor.name,
            'quote_count': quote_totals.get(vendor.pk, {}).get('quote_count', 0),
            'selected_quote_count': quote_totals.get(vendor.pk, {}).get(
                'selected_quote_count',
                0,
            ),
            'purchase_order_count': order_totals.get(vendor.pk, {}).get(
                'purchase_order_count',
                0,
            ),
            'purchase_order_total': order_totals.get(vendor.pk, {}).get(
                'purchase_order_total',
            ),
            'delivery_count': delivery_totals.get(vendor.pk, 0),
        })

    return {
        'filters': {
            'date_from': start_date,
            'date_to': end_date,
            'status': status,
        },
        'procurement_expenditure': {
            'purchase_order_total': orders.aggregate(total=Sum('amount'))['total'] or 0,
            'purchase_order_count': orders.count(),
            'invoice_total': invoices.aggregate(total=Sum('amount'))['total'] or 0,
            'paid_invoice_total': invoices.filter(status='PAID').aggregate(
                total=Sum('amount')
            )['total'] or 0,
        },
        'contract_status': status_totals(contracts, 'value'),
        'vendor_performance': vendors,
        'invoice_status': status_totals(invoices, 'amount'),
        'payment_status': status_totals(payments, 'amount'),
        'requisition_statistics': status_totals(requisitions, 'estimated_value'),
    }
