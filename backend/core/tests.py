from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Contract, Requisition, Vendor, Invoice


class ContractApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='contract-manager',
            password='test-password',
        )

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

    def test_update_and_delete_contract(self):
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
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Contract.objects.filter(id=contract.id).exists())


class RequisitionApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='procurement-manager',
            password='test-password',
        )

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
