from django.contrib import admin
from .models import Contract, Requisition, Vendor, Invoice


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
    list_display = ('name', 'registration_number', 'approved', 'compliance_score')
    search_fields = ('name', 'registration_number')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'vendor', 'contract', 'amount', 'status')

# Register your models here.
