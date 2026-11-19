from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ContractViewSet, RequisitionViewSet, VendorViewSet, InvoiceViewSet

router = DefaultRouter()
router.register('contracts', ContractViewSet)
router.register('requisitions', RequisitionViewSet)
router.register('vendors', VendorViewSet)
router.register('invoices', InvoiceViewSet)

urlpatterns = [path('', include(router.urls))]
