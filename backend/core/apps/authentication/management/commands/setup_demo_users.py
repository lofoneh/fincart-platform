from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.sellers.models import SellerProfile

User = get_user_model()

class Command(BaseCommand):
    help = 'Create demo users for testing'

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                # Create superuser
                if not User.objects.filter(email='admin@fincart.com').exists():
                    admin = User.objects.create_superuser(
                        email='admin@fincart.com',
                        username='admin',
                        phone_number='+1234567890',
                        password='admin123'
                    )
                    admin.email_verified = True
                    admin.phone_verified = True
                    admin.save()
                    self.stdout.write(self.style.SUCCESS('Admin user created'))

                # Create regular buyer
                if not User.objects.filter(email='buyer@example.com').exists():
                    buyer = User.objects.create_user(
                        email='buyer@example.com',
                        username='buyer',
                        phone_number='+1234567891',
                        password='buyer123'
                    )
                    buyer.email_verified = True
                    buyer.is_buyer = True
                    buyer.save()
                    self.stdout.write(self.style.SUCCESS('Buyer user created'))

                # Create seller
                if not User.objects.filter(email='seller@example.com').exists():
                    seller_user = User.objects.create_user(
                        email='seller@example.com',
                        username='seller',
                        phone_number='+1234567892',
                        password='seller123'
                    )
                    seller_user.email_verified = True
                    seller_user.is_seller = True
                    seller_user.save()

                    # Create seller profile
                    SellerProfile.objects.create(
                        user=seller_user,
                        business_name='Demo Store',
                        business_type='retail',
                        business_description='A demo store for testing',
                        approval_status='approved'
                    )
                    self.stdout.write(self.style.SUCCESS('Seller user created'))

                self.stdout.write(
                    self.style.SUCCESS(
                        '\n=== Demo Users Created ===\n'
                        'Admin: admin@fincart.com / admin123\n'
                        'Buyer: buyer@example.com / buyer123\n'
                        'Seller: seller@example.com / seller123\n'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating demo users: {str(e)}')
            )