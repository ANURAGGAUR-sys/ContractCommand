from django.conf import settings
from django.db import models


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

# Create your models here.
