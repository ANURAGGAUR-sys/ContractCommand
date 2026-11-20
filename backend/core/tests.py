from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

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


class FrontendRedirectTests(SimpleTestCase):
    def test_backend_root_redirects_to_frontend(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response['Location'], 'http://127.0.0.1:5173/')


class ContractApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='contract-manager',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.client.force_authenticate(user=self.user)

    def contract_payload(self, **overrides):
        payload = {
            'contract_number': 'CTR-2026-001',
            'title': 'Secure communications upgrade',
            'description': 'Upgrade secure communications equipment.',
            'value': '125000.00',
            'status': 'DRAFT',
            'start_date': '2026-12-01',
            'end_date': '2027-12-31',
            'owner': self.user.id,
        }
        payload.update(overrides)
        return payload

    def test_create_contract(self):
        response = self.client.post(
            reverse('contract-list'),
            self.contract_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Contract.objects.count(), 1)

    def test_reject_contract_with_invalid_date_range(self):
        response = self.client.post(
            reverse('contract-list'),
            self.contract_payload(
                contract_number='CTR-2026-002',
                start_date='2027-12-31',
                end_date='2026-12-01',
            ),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_date', response.data)

    def test_search_contract_by_number(self):
        Contract.objects.create(
            contract_number='CTR-2026-777',
            title='Navigation systems',
            value='90000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=self.user,
        )
        response = self.client.get(
            reverse('contract-list'),
            {'search': 'CTR-2026-777'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_reject_negative_contract_value(self):
        response = self.client.post(
            reverse('contract-list'),
            self.contract_payload(
                contract_number='CTR-2026-003',
                value='-100.00',
            ),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('value', response.data)

    def test_update_contract_and_restrict_delete_to_staff(self):
        contract = Contract.objects.create(
            contract_number='CTR-2026-444',
            title='Lifecycle update test',
            value='10000.00',
            status='DRAFT',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=self.user,
        )
        detail_url = reverse('contract-detail', args=[contract.id])
        update = self.client.patch(
            detail_url,
            {'status': 'ACTIVE'},
            format='json',
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(update.data['status'], 'ACTIVE')
        delete = self.client.delete(detail_url)
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Contract.objects.filter(id=contract.id).exists())


class RequisitionApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='procurement-manager',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Safety Officer'))
        self.client.force_authenticate(user=self.user)

    def test_create_requisition(self):
        response = self.client.post(
            reverse('requisition-list'),
            {
                'requisition_number': 'REQ-2026-001',
                'title': 'Replacement protective equipment',
                'justification': 'Required for current operations.',
                'estimated_value': '45000.00',
                'status': 'SUBMITTED',
                'requested_by': self.user.id,
                'contract': None,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Requisition.objects.count(), 1)

    def test_reject_negative_requisition_value(self):
        response = self.client.post(
            reverse('requisition-list'),
            {
                'requisition_number': 'REQ-2026-002',
                'title': 'Invalid requisition',
                'justification': 'Test validation.',
                'estimated_value': '-1.00',
                'status': 'DRAFT',
                'requested_by': self.user.id,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('estimated_value', response.data)


class VendorApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='safety-officer',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Safety Officer'))
        self.client.force_authenticate(user=self.user)

    def vendor_payload(self, **overrides):
        payload = {
            'name': 'Aerospace Systems Ltd',
            'registration_number': 'VEN-2026-001',
            'contact_email': 'supplier@example.com',
            'phone': '+1-555-0100',
            'compliance_score': 85,
            'approved': True,
        }
        payload.update(overrides)
        return payload

    def test_create_vendor(self):
        response = self.client.post(
            reverse('vendor-list'),
            self.vendor_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vendor.objects.count(), 1)

    def test_reject_invalid_compliance_score(self):
        response = self.client.post(
            reverse('vendor-list'),
            self.vendor_payload(
                registration_number='VEN-2026-002',
                compliance_score=101,
            ),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('compliance_score', response.data)

    def test_search_vendor_by_name(self):
        Vendor.objects.create(
            name='Precision Components',
            registration_number='VEN-2026-777',
            contact_email='precision@example.com',
            compliance_score=92,
            approved=True,
        )
        response = self.client.get(
            reverse('vendor-list'),
            {'search': 'Precision Components'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class InvoiceApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='invoice-manager',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.client.force_authenticate(user=self.user)
        self.contract = Contract.objects.create(
            contract_number='CTR-2026-500',
            title='Radar maintenance',
            value='500000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=self.user,
        )
        self.vendor = Vendor.objects.create(
            name='Radar Services Ltd',
            registration_number='VEN-2026-500',
            contact_email='billing@radar.example',
            compliance_score=95,
            approved=True,
        )

    def invoice_payload(self, **overrides):
        payload = {
            'invoice_number': 'INV-2026-500',
            'vendor': self.vendor.id,
            'contract': self.contract.id,
            'amount': '12500.00',
            'status': 'PENDING',
            'invoice_date': '2026-11-01',
            'due_date': '2026-11-30',
        }
        payload.update(overrides)
        return payload

    def test_create_invoice(self):
        response = self.client.post(
            reverse('invoice-list'),
            self.invoice_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_reject_negative_amount(self):
        response = self.client.post(
            reverse('invoice-list'),
            self.invoice_payload(invoice_number='INV-2026-501', amount='-1.00'),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', response.data)

    def test_reject_due_date_before_invoice_date(self):
        response = self.client.post(
            reverse('invoice-list'),
            self.invoice_payload(
                invoice_number='INV-2026-502',
                invoice_date='2026-11-30',
                due_date='2026-11-01',
            ),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('due_date', response.data)


class AuthenticationApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='role-user',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.client = APIClient()

    def test_login_returns_jwt_and_token_authenticates_api(self):
        login_response = self.client.post(
            reverse('auth-token'),
            {'username': 'role-user', 'password': 'test-password'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('Contracts Manager', login_response.data['user']['roles'])
        self.assertIn(
            'create',
            login_response.data['user']['capabilities']['contracts'],
        )
        self.assertIn('access', login_response.data)
        self.assertIn('refresh', login_response.data)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )
        self.assertEqual(
            self.client.get(reverse('contract-list')).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(reverse('auth-me')).status_code,
            status.HTTP_200_OK,
        )

    def test_login_rejects_bad_credentials(self):
        response = self.client.post(
            reverse('auth-token'),
            {'username': 'role-user', 'password': 'wrong-password'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_rejects_account_without_application_role(self):
        get_user_model().objects.create_user(
            username='no-role-user',
            password='test-password',
        )
        response = self.client.post(
            reverse('auth-token'),
            {'username': 'no-role-user', 'password': 'test-password'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_refresh_token_returns_new_access_token(self):
        login_response = self.client.post(
            reverse('auth-token'),
            {'username': 'role-user', 'password': 'test-password'},
            format='json',
        )
        response = self.client.post(
            reverse('auth-token-refresh'),
            {'refresh': login_response.data['refresh']},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(
            reverse('auth-token'),
            {'username': 'role-user', 'password': 'test-password'},
            format='json',
        )
        blacklist_response = self.client.post(
            reverse('auth-token-blacklist'),
            {'refresh': login_response.data['refresh']},
            format='json',
        )
        self.assertEqual(blacklist_response.status_code, status.HTTP_200_OK)
        refresh_response = self.client.post(
            reverse('auth-token-refresh'),
            {'refresh': login_response.data['refresh']},
            format='json',
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)


class RoleAuthorizationApiTests(APITestCase):
    def test_anonymous_user_cannot_read_records(self):
        self.assertEqual(
            self.client.get(reverse('contract-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_authenticated_user_without_role_is_denied(self):
        user = get_user_model().objects.create_user(
            username='unassigned-user',
            password='test-password',
        )
        self.client.force_authenticate(user=user)
        self.assertEqual(
            self.client.get(reverse('contract-list')).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_manager_can_create_but_cannot_delete_contracts(self):
        user = get_user_model().objects.create_user(
            username='role-manager',
            password='test-password',
        )
        user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.client.force_authenticate(user=user)
        response = self.client.post(
            reverse('contract-list'),
            {
                'contract_number': 'CTR-ROLE-001',
                'title': 'Role protected contract',
                'value': '1000.00',
                'start_date': '2026-01-01',
                'end_date': '2026-12-31',
                'status': 'DRAFT',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contract = Contract.objects.get(contract_number='CTR-ROLE-001')
        self.assertEqual(contract.owner_id, user.id)
        response = self.client.delete(
            reverse('contract-detail', args=[contract.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_can_delete_contracts(self):
        user = get_user_model().objects.create_user(
            username='administrator',
            password='test-password',
            is_staff=True,
        )
        contract = Contract.objects.create(
            contract_number='CTR-ADMIN-001',
            title='Admin deletion test',
            value='1000.00',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=user,
        )
        self.client.force_authenticate(user=user)
        response = self.client.delete(
            reverse('contract-detail', args=[contract.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class RoleDataScopeApiTests(APITestCase):
    def test_requester_sees_only_own_requisitions_and_cannot_read_vendors(self):
        requester = get_user_model().objects.create_user(
            username='requester-user',
            password='test-password',
        )
        requester.groups.add(Group.objects.get(name='Requester'))
        other_user = get_user_model().objects.create_user(
            username='other-requester',
            password='test-password',
        )
        own_requisition = Requisition.objects.create(
            requisition_number='REQ-OWN-001',
            title='Requester own item',
            justification='Required by this requester.',
            estimated_value='100.00',
            status='DRAFT',
            requested_by=requester,
        )
        Requisition.objects.create(
            requisition_number='REQ-OTHER-001',
            title='Other requester item',
            justification='Required by another requester.',
            estimated_value='200.00',
            status='DRAFT',
            requested_by=other_user,
        )
        self.client.force_authenticate(user=requester)

        response = self.client.get(reverse('requisition-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['requisition_number'] for item in response.data],
            ['REQ-OWN-001'],
        )
        status_update = self.client.patch(
            reverse('requisition-detail', args=[own_requisition.id]),
            {'status': 'APPROVED'},
            format='json',
        )
        self.assertEqual(status_update.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self.client.get(reverse('vendor-list')).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_vendor_sees_only_linked_vendor_and_invoice_records(self):
        vendor_user = get_user_model().objects.create_user(
            username='vendor-user',
            password='test-password',
        )
        vendor_user.groups.add(
            Group.objects.get(name='Vendor'),
            Group.objects.get(name='Requester'),
        )
        own_vendor = Vendor.objects.create(
            name='Own vendor',
            registration_number='VEN-OWN-001',
            contact_email='own@example.com',
            user=vendor_user,
        )
        Vendor.objects.create(
            name='Other vendor',
            registration_number='VEN-OTHER-001',
            contact_email='other@example.com',
        )
        contract = Contract.objects.create(
            contract_number='CTR-VENDOR-001',
            title='Vendor invoice contract',
            value='1000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=vendor_user,
        )
        Invoice.objects.create(
            invoice_number='INV-VENDOR-001',
            vendor=own_vendor,
            contract=contract,
            amount='100.00',
            status='PENDING',
            invoice_date='2026-10-01',
            due_date='2026-11-01',
        )
        self.client.force_authenticate(user=vendor_user)

        vendors = self.client.get(reverse('vendor-list'))
        invoices = self.client.get(reverse('invoice-list'))

        self.assertEqual(vendors.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['registration_number'] for item in vendors.data],
            ['VEN-OWN-001'],
        )
        self.assertEqual(invoices.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['invoice_number'] for item in invoices.data],
            ['INV-VENDOR-001'],
        )
        self.assertEqual(
            self.client.get(reverse('contract-list')).status_code,
            status.HTTP_200_OK,
        )


class RolePermissionMatrixApiTests(APITestCase):
    def test_approver_is_read_only(self):
        user = get_user_model().objects.create_user(
            username='approver-user',
            password='test-password',
        )
        user.groups.add(Group.objects.get(name='Approver'))
        self.client.force_authenticate(user=user)

        self.assertEqual(
            self.client.get(reverse('contract-list')).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(reverse('contract-list'), {}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_finance_officer_can_update_but_not_create_invoices(self):
        user = get_user_model().objects.create_user(
            username='finance-user',
            password='test-password',
        )
        user.groups.add(Group.objects.get(name='Finance Officer'))
        vendor = Vendor.objects.create(
            name='Finance test vendor',
            registration_number='VEN-FIN-001',
            contact_email='finance@example.com',
        )
        contract = Contract.objects.create(
            contract_number='CTR-FIN-001',
            title='Finance test contract',
            value='1000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=user,
        )
        invoice = Invoice.objects.create(
            invoice_number='INV-FIN-001',
            vendor=vendor,
            contract=contract,
            amount='100.00',
            status='PENDING',
            invoice_date='2026-10-01',
            due_date='2026-11-01',
        )
        self.client.force_authenticate(user=user)

        update = self.client.patch(
            reverse('invoice-detail', args=[invoice.id]),
            {'status': 'APPROVED'},
            format='json',
        )

        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(reverse('invoice-list'), {}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )


class QuotationWorkflowApiTests(APITestCase):
    def setUp(self):
        self.procurement_user = get_user_model().objects.create_user(
            username='quotation-procurement',
            password='test-password',
        )
        self.procurement_user.groups.add(Group.objects.get(name='Procurement Officer'))
        self.vendor_user = get_user_model().objects.create_user(
            username='quotation-vendor',
            password='test-password',
        )
        self.vendor_user.groups.add(Group.objects.get(name='Vendor'))
        self.vendor = Vendor.objects.create(
            name='Invited vendor',
            registration_number='VEN-QUOTE-001',
            contact_email='invited@example.com',
            approved=True,
            user=self.vendor_user,
        )
        self.requisition = Requisition.objects.create(
            requisition_number='REQ-QUOTE-001',
            title='Quotation test requisition',
            justification='Compare vendor proposals.',
            estimated_value='1000.00',
            status='APPROVED',
            requested_by=self.procurement_user,
        )
        self.client.force_authenticate(user=self.procurement_user)
        response = self.client.post(
            reverse('quotationrequest-list'),
            {
                'request_number': 'RFQ-2026-001',
                'requisition': self.requisition.id,
                'title': 'Supply of protective equipment',
                'description': 'Submit price and delivery proposal.',
                'status': 'OPEN',
                'invited_vendors': [self.vendor.id],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.quotation_request = QuotationRequest.objects.get(
            request_number='RFQ-2026-001'
        )

    def test_invited_vendor_can_submit_quote_but_uninvited_vendor_cannot(self):
        vendor_client = APIClient()
        vendor_client.force_authenticate(user=self.vendor_user)
        response = vendor_client.post(
            reverse('vendorquote-list'),
            {
                'quotation_request': self.quotation_request.id,
                'amount': '875.00',
                'proposal': 'Delivery within 30 days.',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['vendor'], self.vendor.id)
        self.assertEqual(VendorQuote.objects.count(), 1)

        uninvited_user = get_user_model().objects.create_user(
            username='uninvited-vendor',
            password='test-password',
        )
        uninvited_user.groups.add(Group.objects.get(name='Vendor'))
        Vendor.objects.create(
            name='Uninvited vendor',
            registration_number='VEN-QUOTE-002',
            contact_email='uninvited@example.com',
            user=uninvited_user,
        )
        uninvited_client = APIClient()
        uninvited_client.force_authenticate(user=uninvited_user)
        rejected = uninvited_client.post(
            reverse('vendorquote-list'),
            {
                'quotation_request': self.quotation_request.id,
                'amount': '900.00',
            },
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(VendorQuote.objects.count(), 1)


class PurchaseOrderWorkflowApiTests(APITestCase):
    def test_purchase_order_requires_approved_vendor_and_requisition(self):
        procurement_user = get_user_model().objects.create_user(
            username='po-validation-procurement',
            password='test-password',
        )
        procurement_user.groups.add(Group.objects.get(name='Procurement Officer'))
        vendor = Vendor.objects.create(
            name='Unapproved PO vendor',
            registration_number='VEN-PO-VALIDATION',
            contact_email='unapproved-po@example.com',
        )
        requisition = Requisition.objects.create(
            requisition_number='REQ-PO-VALIDATION',
            title='Validation requisition',
            justification='Must be approved before order creation.',
            estimated_value='1000.00',
            status='APPROVED',
            requested_by=procurement_user,
        )
        client = APIClient()
        client.force_authenticate(user=procurement_user)

        response = client.post(
            reverse('purchaseorder-list'),
            {
                'po_number': 'PO-VALIDATION-001',
                'requisition': requisition.id,
                'vendor': vendor.id,
                'amount': '950.00',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('vendor', response.data)

        vendor.approved = True
        vendor.save(update_fields=['approved'])
        draft_requisition = Requisition.objects.create(
            requisition_number='REQ-PO-DRAFT-VALIDATION',
            title='Draft validation requisition',
            justification='Must not progress to an order.',
            estimated_value='1000.00',
            status='DRAFT',
            requested_by=procurement_user,
        )
        response = client.post(
            reverse('purchaseorder-list'),
            {
                'po_number': 'PO-VALIDATION-002',
                'requisition': draft_requisition.id,
                'vendor': vendor.id,
                'amount': '950.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('requisition', response.data)

    def test_delivered_delivery_requires_a_delivered_date(self):
        procurement_user = get_user_model().objects.create_user(
            username='delivery-procurement',
            password='test-password',
        )
        procurement_user.groups.add(Group.objects.get(name='Procurement Officer'))
        vendor = Vendor.objects.create(
            name='Delivery vendor',
            registration_number='VEN-DELIVERY-001',
            contact_email='delivery@example.com',
            approved=True,
        )
        requisition = Requisition.objects.create(
            requisition_number='REQ-DELIVERY-001',
            title='Delivery test requisition',
            justification='Approved for delivery.',
            estimated_value='1000.00',
            status='APPROVED',
            requested_by=procurement_user,
        )
        purchase_order = PurchaseOrder.objects.create(
            po_number='PO-DELIVERY-001',
            requisition=requisition,
            vendor=vendor,
            amount='950.00',
            status='APPROVED',
            created_by=procurement_user,
        )
        client = APIClient()
        client.force_authenticate(user=procurement_user)

        rejected = client.post(
            reverse('delivery-list'),
            {
                'delivery_number': 'DEL-2026-001',
                'purchase_order': purchase_order.id,
                'status': 'DELIVERED',
            },
            format='json',
        )
        accepted = client.post(
            reverse('delivery-list'),
            {
                'delivery_number': 'DEL-2026-002',
                'purchase_order': purchase_order.id,
                'status': 'DELIVERED',
                'delivered_date': '2026-11-20',
            },
            format='json',
        )

        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('delivered_date', rejected.data)
        self.assertEqual(accepted.status_code, status.HTTP_201_CREATED)

    def test_purchase_order_requires_approvers_and_all_approvals_to_approve(self):
        procurement_user = get_user_model().objects.create_user(
            username='po-procurement',
            password='test-password',
        )
        procurement_user.groups.add(Group.objects.get(name='Procurement Officer'))
        approvers = []
        for username in ('po-approver-one', 'po-approver-two'):
            approver = get_user_model().objects.create_user(
                username=username,
                password='test-password',
            )
            approver.groups.add(Group.objects.get(name='Approver'))
            approvers.append(approver)
        vendor = Vendor.objects.create(
            name='Approved PO vendor',
            registration_number='VEN-PO-001',
            contact_email='po-vendor@example.com',
            approved=True,
        )
        requisition = Requisition.objects.create(
            requisition_number='REQ-PO-001',
            title='Purchase-order test requisition',
            justification='Approved requirement.',
            estimated_value='1000.00',
            status='APPROVED',
            requested_by=procurement_user,
        )
        procurement_client = APIClient()
        procurement_client.force_authenticate(user=procurement_user)
        response = procurement_client.post(
            reverse('purchaseorder-list'),
            {
                'po_number': 'PO-2026-001',
                'requisition': requisition.id,
                'vendor': vendor.id,
                'amount': '950.00',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order_id = response.data['id']
        self.assertEqual(response.data['status'], 'DRAFT')
        submitted = procurement_client.post(
            reverse('purchaseorder-submit', args=[order_id]),
            {},
            format='json',
        )
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        self.assertEqual(submitted.data['status'], 'PENDING_APPROVAL')
        self.assertEqual(Approval.objects.filter(purchase_order_id=order_id).count(), 2)
        self.assertEqual(
            Notification.objects.filter(
                notification_type='PENDING_APPROVAL',
                related_id__in=Approval.objects.filter(
                    purchase_order_id=order_id,
                ).values('id'),
            ).count(),
            2,
        )

        first_client = APIClient()
        first_client.force_authenticate(user=approvers[0])
        first_approval = Approval.objects.get(
            purchase_order_id=order_id,
            approver=approvers[0],
        )
        first_decision = first_client.post(
            reverse('approval-decide', args=[first_approval.id]),
            {'decision': 'APPROVED', 'comments': 'Within budget.'},
            format='json',
        )
        self.assertEqual(first_decision.status_code, status.HTTP_200_OK)
        self.assertEqual(
            PurchaseOrder.objects.get(pk=order_id).status,
            'PENDING_APPROVAL',
        )

        second_client = APIClient()
        second_client.force_authenticate(user=approvers[1])
        second_approval = Approval.objects.get(
            purchase_order_id=order_id,
            approver=approvers[1],
        )
        second_decision = second_client.post(
            reverse('approval-decide', args=[second_approval.id]),
            {'decision': 'APPROVED'},
            format='json',
        )
        self.assertEqual(second_decision.status_code, status.HTTP_200_OK)
        self.assertEqual(
            PurchaseOrder.objects.get(pk=order_id).status,
            'APPROVED',
        )
        self.assertTrue(
            Notification.objects.filter(
                user=procurement_user,
                notification_type='APPROVAL_DECISION',
            ).exists()
        )

    def test_approver_cannot_decide_another_users_approval(self):
        procurement_user = get_user_model().objects.create_user(
            username='po-procurement-scope',
            password='test-password',
        )
        procurement_user.groups.add(Group.objects.get(name='Procurement Officer'))
        assigned_approver = get_user_model().objects.create_user(
            username='assigned-approver',
            password='test-password',
        )
        assigned_approver.groups.add(Group.objects.get(name='Approver'))
        other_approver = get_user_model().objects.create_user(
            username='other-approver',
            password='test-password',
        )
        other_approver.groups.add(Group.objects.get(name='Approver'))
        vendor = Vendor.objects.create(
            name='Scoped PO vendor',
            registration_number='VEN-PO-002',
            contact_email='scoped@example.com',
            approved=True,
        )
        requisition = Requisition.objects.create(
            requisition_number='REQ-PO-002',
            title='Scoped purchase-order requisition',
            justification='Approved requirement.',
            estimated_value='1000.00',
            status='APPROVED',
            requested_by=procurement_user,
        )
        order = PurchaseOrder.objects.create(
            po_number='PO-2026-002',
            requisition=requisition,
            vendor=vendor,
            amount='950.00',
            status='PENDING_APPROVAL',
            created_by=procurement_user,
        )
        approval = Approval.objects.create(
            purchase_order=order,
            approver=assigned_approver,
        )
        client = APIClient()
        client.force_authenticate(user=other_approver)

        response = client.post(
            reverse('approval-decide', args=[approval.id]),
            {'decision': 'APPROVED'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'PENDING')


class PaymentSessionApiTests(APITestCase):
    def setUp(self):
        self.finance_user = get_user_model().objects.create_user(
            username='payment-finance',
            password='test-password',
        )
        self.finance_user.groups.add(Group.objects.get(name='Finance Officer'))
        vendor = Vendor.objects.create(
            name='Payment vendor',
            registration_number='VEN-PAYMENT-001',
            contact_email='payment@example.com',
            approved=True,
        )
        contract = Contract.objects.create(
            contract_number='CTR-PAYMENT-001',
            title='Payment test contract',
            value='1000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2026-12-31',
            owner=self.finance_user,
        )
        self.invoice = Invoice.objects.create(
            invoice_number='INV-PAYMENT-001',
            vendor=vendor,
            contract=contract,
            amount='275.00',
            status='APPROVED',
            invoice_date='2026-10-01',
            due_date='2026-11-01',
        )
        self.client.force_authenticate(user=self.finance_user)

    def test_demo_session_expires_after_ten_minutes_and_completes_invoice(self):
        now = timezone.now()
        response = self.client.post(
            reverse('paymentsession-list'),
            {'invoice': self.invoice.id},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment_session = PaymentSession.objects.get(pk=response.data['id'])
        self.assertGreater(payment_session.expires_at, now)
        self.assertLessEqual(
            payment_session.expires_at - now,
            timedelta(minutes=10, seconds=1),
        )
        completed = self.client.post(
            reverse('paymentsession-complete', args=[payment_session.id]),
            {},
            format='json',
        )

        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        payment_session.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment_session.status, 'COMPLETED')
        self.assertEqual(self.invoice.status, 'PAID')
        self.assertTrue(
            Notification.objects.filter(
                user=self.finance_user,
                notification_type='PAYMENT_UPDATE',
            ).exists()
        )

    def test_expired_demo_session_cannot_complete(self):
        payment_session = PaymentSession.objects.create(
            invoice=self.invoice,
            amount=self.invoice.amount,
            expires_at=timezone.now() - timedelta(seconds=1),
            created_by=self.finance_user,
        )
        listed = self.client.get(reverse('paymentsession-list'))

        response = self.client.post(
            reverse('paymentsession-complete', args=[payment_session.id]),
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(listed.data[0]['status'], 'EXPIRED')
        payment_session.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(payment_session.status, 'EXPIRED')
        self.assertEqual(self.invoice.status, 'APPROVED')

    def test_demo_session_is_cancelled_if_invoice_amount_changes(self):
        created = self.client.post(
            reverse('paymentsession-list'),
            {'invoice': self.invoice.id},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        payment_session = PaymentSession.objects.get(pk=created.data['id'])
        self.invoice.amount = '300.00'
        self.invoice.save(update_fields=['amount'])

        response = self.client.post(
            reverse('paymentsession-complete', args=[payment_session.id]),
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payment_session.refresh_from_db()
        self.assertEqual(payment_session.status, 'CANCELLED')


class DocumentApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='document-manager',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.contract = Contract.objects.create(
            contract_number='CTR-DOCUMENT-001',
            title='Document test contract',
            value='1000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2027-01-01',
            owner=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def upload(self, file=None, **overrides):
        payload = {
            'document_type': 'CONTRACT',
            'contract': self.contract.id,
            'file': file or SimpleUploadedFile(
                'contract.png',
                b'\x89PNG\r\n\x1a\nsample-image-data',
                content_type='image/png',
            ),
        }
        payload.update(overrides)
        return self.client.post(
            reverse('document-list'),
            payload,
            format='multipart',
        )

    def test_upload_and_download_are_audited_and_private(self):
        response = self.upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get()
        self.addCleanup(document.file.storage.delete, document.file.name)
        self.assertNotIn('file', response.data)
        self.assertEqual(document.original_filename, 'contract.png')
        self.assertEqual(document.size_bytes, len(b'\x89PNG\r\n\x1a\nsample-image-data'))
        with self.assertRaises(ValueError):
            _ = document.file.url

        downloaded = self.client.get(
            reverse('document-download', args=[document.id])
        )
        self.assertEqual(downloaded.status_code, status.HTTP_200_OK)
        self.assertIn('attachment', downloaded['Content-Disposition'])
        self.assertEqual(
            b''.join(downloaded.streaming_content),
            b'\x89PNG\r\n\x1a\nsample-image-data',
        )
        self.assertEqual(
            AuditLog.objects.filter(
                action='UPLOAD',
                object_id=str(document.id),
            ).count(),
            1,
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action='READ',
                object_id=str(document.id),
            ).exists()
        )

        vendor_user = get_user_model().objects.create_user(
            username='document-vendor',
            password='test-password',
        )
        vendor_user.groups.add(Group.objects.get(name='Vendor'))
        Vendor.objects.create(
            name='Document vendor',
            registration_number='VEN-DOCUMENT-001',
            contact_email='document@example.com',
            user=vendor_user,
        )
        vendor_client = APIClient()
        vendor_client.force_authenticate(user=vendor_user)
        self.assertEqual(
            vendor_client.get(reverse('document-list')).data,
            [],
        )
        self.assertEqual(
            vendor_client.get(
                reverse('document-download', args=[document.id])
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_reject_invalid_file_and_disallowed_role_upload(self):
        maximum_size = 10 * 1024 * 1024
        at_limit = self.upload(
            file=SimpleUploadedFile(
                'at-limit.txt',
                b'x' * maximum_size,
                content_type='text/plain',
            )
        )
        self.assertEqual(at_limit.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(original_filename='at-limit.txt')
        self.addCleanup(document.file.storage.delete, document.file.name)
        self.assertEqual(document.size_bytes, maximum_size)

        invalid = self.upload(
            file=SimpleUploadedFile(
                'not-a-pdf.pdf',
                b'not a PDF',
                content_type='application/pdf',
            )
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        oversized = self.upload(
            file=SimpleUploadedFile(
                'too-large.txt',
                b'x' * (10 * 1024 * 1024 + 1),
                content_type='text/plain',
            )
        )
        self.assertEqual(oversized.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', oversized.data)

        safety_user = get_user_model().objects.create_user(
            username='document-safety',
            password='test-password',
        )
        safety_user.groups.add(Group.objects.get(name='Safety Officer'))
        safety_client = APIClient()
        safety_client.force_authenticate(user=safety_user)
        forbidden = safety_client.post(
            reverse('document-list'),
            {
                'document_type': 'CONTRACT',
                'contract': self.contract.id,
                'file': SimpleUploadedFile(
                    'valid.png',
                    b'\x89PNG\r\n\x1a\ncontent',
                    content_type='image/png',
                ),
            },
            format='multipart',
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='notification-manager',
            password='test-password',
        )
        self.user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.other_user = get_user_model().objects.create_user(
            username='notification-other',
            password='test-password',
        )
        self.other_user.groups.add(Group.objects.get(name='Contracts Manager'))
        self.notification = Notification.objects.create(
            user=self.user,
            notification_type='PENDING_APPROVAL',
            message='A purchase order requires your approval.',
        )
        self.other_notification = Notification.objects.create(
            user=self.other_user,
            notification_type='PAYMENT_UPDATE',
            message='A payment was completed.',
        )
        self.client.force_authenticate(user=self.user)

    def test_notifications_are_scoped_and_can_only_be_marked_read(self):
        response = self.client.get(reverse('notification-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['id'] for item in response.data],
            [self.notification.id],
        )

        marked = self.client.patch(
            reverse('notification-mark-read', args=[self.notification.id]),
            {},
            format='json',
        )
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(marked.data['read_at'])
        self.assertEqual(
            self.client.patch(
                reverse('notification-mark-read', args=[self.other_notification.id]),
                {},
                format='json',
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                reverse('notification-list'),
                {},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_requisition_decision_and_invoice_submission_notify_users(self):
        requester = get_user_model().objects.create_user(
            username='decision-requester',
            password='test-password',
        )
        requester.groups.add(Group.objects.get(name='Requester'))
        requisition = Requisition.objects.create(
            requisition_number='REQ-NOTIFICATION-001',
            title='Decision notification',
            justification='Notify requester of a decision.',
            estimated_value='100.00',
            status='SUBMITTED',
            requested_by=requester,
        )
        decision = self.client.patch(
            reverse('requisition-detail', args=[requisition.id]),
            {'status': 'REJECTED'},
            format='json',
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Notification.objects.filter(
                user=requester,
                notification_type='REQUISITION_DECISION',
            ).exists()
        )

        finance_user = get_user_model().objects.create_user(
            username='invoice-notification-finance',
            password='test-password',
        )
        finance_user.groups.add(Group.objects.get(name='Finance Officer'))
        vendor = Vendor.objects.create(
            name='Invoice notification vendor',
            registration_number='VEN-NOTIFICATION-001',
            contact_email='notify@example.com',
        )
        contract = Contract.objects.create(
            contract_number='CTR-NOTIFICATION-001',
            title='Invoice notification contract',
            value='1000.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2027-01-01',
            owner=self.user,
        )
        submitted = self.client.post(
            reverse('invoice-list'),
            {
                'invoice_number': 'INV-NOTIFICATION-001',
                'vendor': vendor.id,
                'contract': contract.id,
                'amount': '90.00',
                'invoice_date': timezone.localdate().isoformat(),
                'due_date': (timezone.localdate() + timedelta(days=30)).isoformat(),
            },
            format='json',
        )
        self.assertEqual(submitted.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(
                user=finance_user,
                notification_type='INVOICE_SUBMITTED',
            ).exists()
        )

    def test_contract_expiration_command_is_idempotent(self):
        today = timezone.localdate()
        Contract.objects.create(
            contract_number='CTR-EXPIRING-001',
            title='Expiring contract',
            value='1000.00',
            status='ACTIVE',
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=10),
            owner=self.user,
        )

        call_command('send_contract_expiration_notifications', stdout=None)
        call_command('send_contract_expiration_notifications', stdout=None)

        self.assertEqual(
            Notification.objects.filter(
                user=self.user,
                notification_type='CONTRACT_EXPIRING',
            ).count(),
            1,
        )


class AuditAndReportApiTests(APITestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username='audit-manager',
            password='test-password',
        )
        self.manager.groups.add(Group.objects.get(name='Contracts Manager'))
        self.contract = Contract.objects.create(
            contract_number='CTR-REPORT-001',
            title='Report test contract',
            value='1200.00',
            status='ACTIVE',
            start_date='2026-01-01',
            end_date='2027-01-01',
            owner=self.manager,
        )
        self.vendor = Vendor.objects.create(
            name='Report vendor',
            registration_number='VEN-REPORT-001',
            contact_email='report@example.com',
            approved=True,
        )
        self.requisition = Requisition.objects.create(
            requisition_number='REQ-REPORT-001',
            title='Report requisition',
            justification='Report fixture.',
            estimated_value='750.00',
            status='APPROVED',
            requested_by=self.manager,
        )
        self.order = PurchaseOrder.objects.create(
            po_number='PO-REPORT-001',
            requisition=self.requisition,
            vendor=self.vendor,
            amount='700.00',
            status='APPROVED',
            created_by=self.manager,
        )
        self.invoice = Invoice.objects.create(
            invoice_number='INV-REPORT-001',
            vendor=self.vendor,
            contract=self.contract,
            purchase_order=self.order,
            amount='650.00',
            status='PAID',
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=10),
        )
        self.client.force_authenticate(user=self.manager)

    def test_audit_history_is_read_only_and_authorized(self):
        response = self.client.post(
            reverse('contract-list'),
            {
                'contract_number': 'CTR-AUDIT-001',
                'title': 'Audited contract',
                'value': '100.00',
                'status': 'DRAFT',
                'start_date': '2026-01-01',
                'end_date': '2026-12-31',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        audit = AuditLog.objects.get(
            entity_type='core.Contract',
            object_id=str(response.data['id']),
            action='CREATE',
        )
        self.assertEqual(audit.user_id, self.manager.id)

        listed = self.client.get(reverse('auditlog-list'))
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item['id'] == audit.id for item in listed.data))
        self.assertEqual(
            self.client.patch(
                reverse('auditlog-detail', args=[audit.id]),
                {'action': 'DELETE'},
                format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        audit.action = 'DELETE'
        with self.assertRaises(ValueError):
            audit.save()

        safety_user = get_user_model().objects.create_user(
            username='audit-safety',
            password='test-password',
        )
        safety_user.groups.add(Group.objects.get(name='Safety Officer'))
        client = APIClient()
        client.force_authenticate(user=safety_user)
        self.assertEqual(
            client.get(reverse('auditlog-list')).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_filtered_report_summary_and_csv_export(self):
        query = {
            'date_from': timezone.localdate().isoformat(),
            'date_to': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'status': 'PAID',
        }
        summary = self.client.get(reverse('report-list'), query)
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data['invoice_status'][0]['status'], 'PAID')
        self.assertEqual(
            str(summary.data['procurement_expenditure']['paid_invoice_total']),
            '650',
        )

        export = self.client.get(
            reverse('report-export'),
            {**query, 'report': 'summary'},
        )
        self.assertEqual(export.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', export['Content-Type'])
        self.assertIn(',invoices,PAID,', export.content.decode())

        invalid = self.client.get(
            reverse('report-list'),
            {'date_from': 'not-a-date'},
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
