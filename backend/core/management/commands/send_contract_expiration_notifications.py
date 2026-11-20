from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Contract, Notification
from core.services import create_notification


class Command(BaseCommand):
    help = 'Notify contract owners and managers about contracts expiring soon.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Notify about active contracts expiring within this many days.',
        )

    def handle(self, *args, **options):
        days = options['days']
        if days < 0:
            raise CommandError('--days must be zero or greater.')

        today = timezone.localdate()
        deadline = today + timedelta(days=days)
        managers = list(
            get_user_model().objects.filter(
                is_active=True,
                groups__name='Contracts Manager',
            ).distinct()
        )
        notifications_created = 0

        contracts = Contract.objects.filter(
            status='ACTIVE',
            end_date__gte=today,
            end_date__lte=deadline,
        ).select_related('owner')
        for contract in contracts:
            recipients = {contract.owner}
            recipients.update(managers)
            for user in recipients:
                if not user.is_active:
                    continue
                dedupe_key = (
                    f'contract-expiring:{contract.pk}:'
                    f'{contract.end_date.isoformat()}'
                )
                created = not Notification.objects.filter(
                    user=user,
                    dedupe_key=dedupe_key,
                ).exists()
                create_notification(
                    user,
                    'CONTRACT_EXPIRING',
                    f'Contract {contract.contract_number} expires on {contract.end_date}.',
                    related_object=contract,
                    dedupe_key=dedupe_key,
                )
                notifications_created += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f'Created {notifications_created} contract expiration notification(s).'
            )
        )
