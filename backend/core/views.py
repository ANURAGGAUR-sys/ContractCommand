from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from .models import Contract, Requisition, Vendor, Invoice
from .serializers import (
    ContractSerializer, RequisitionSerializer, VendorSerializer, InvoiceSerializer,
)


class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.select_related('owner').all()
    serializer_class = ContractSerializer
    filter_backends = [SearchFilter]
    search_fields = ['contract_number', 'title', 'status']


class RequisitionViewSet(viewsets.ModelViewSet):
    queryset = Requisition.objects.select_related('requested_by', 'contract').all()
    serializer_class = RequisitionSerializer
    filter_backends = [SearchFilter]
    search_fields = ['requisition_number', 'title', 'status']


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name', 'registration_number']


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('vendor', 'contract').all()
    serializer_class = InvoiceSerializer
    filter_backends = [SearchFilter]
    search_fields = ['invoice_number', 'status']

# Create your views here.
