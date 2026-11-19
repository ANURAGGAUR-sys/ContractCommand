from rest_framework import serializers
from .models import Contract, Requisition, Vendor, Invoice


class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date cannot be before start date.'
            })
        return attrs


class RequisitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requisition
        fields = '__all__'
        read_only_fields = ('created_at',)


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'
        read_only_fields = ('created_at',)

    def validate_compliance_score(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError(
                'Compliance score must be between 0 and 100.'
            )
        return value


class InvoiceSerializer(serializers.ModelSerializer):
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
        if invoice_date and due_date and due_date < invoice_date:
            raise serializers.ValidationError({
                'due_date': 'Due date cannot be before invoice date.'
            })
        return attrs
