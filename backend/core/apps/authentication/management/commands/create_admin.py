from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

class Command(BaseCommand):
    help = 'Create an admin/superuser'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email address')
        parser.add_argument('--username', type=str, help='Admin username')
        parser.add_argument('--phone', type=str, help='Admin phone number')
        parser.add_argument('--password', type=str, help='Admin password')
        parser.add_argument('--superuser', action='store_true', help='Create superuser instead of staff')

    def handle(self, *args, **options):
        email = options.get('email')
        username = options.get('username')
        phone = options.get('phone')
        password = options.get('password')
        is_superuser = options.get('superuser', False)

        # Interactive input if not provided
        if not email:
            email = input('Email address: ')
        
        if not username:
            username = input('Username: ')
        
        if not phone:
            phone = input('Phone number: ')
        
        if not password:
            import getpass
            password = getpass.getpass('Password: ')
            confirm_password = getpass.getpass('Confirm password: ')
            
            if password != confirm_password:
                self.stdout.write(
                    self.style.ERROR('Passwords do not match!')
                )
                return

        # Validate required fields
        if not all([email, username, phone, password]):
            self.stdout.write(
                self.style.ERROR('All fields are required!')
            )
            return

        try:
            with transaction.atomic():
                # Check if user already exists
                if User.objects.filter(email=email).exists():
                    self.stdout.write(
                        self.style.ERROR(f'User with email {email} already exists!')
                    )
                    return

                if User.objects.filter(phone_number=phone).exists():
                    self.stdout.write(
                        self.style.ERROR(f'User with phone {phone} already exists!')
                    )
                    return

                # Create user
                if is_superuser:
                    user = User.objects.create_superuser(
                        email=email,
                        username=username,
                        phone_number=phone,
                        password=password
                    )
                    user_type = "Superuser"
                else:
                    user = User.objects.create_user(
                        email=email,
                        username=username,
                        phone_number=phone,
                        password=password,
                        is_staff=True
                    )
                    user_type = "Admin"

                # Mark as verified
                user.email_verified = True
                user.phone_verified = True
                user.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f'{user_type} created successfully!\n'
                        f'Email: {email}\n'
                        f'Username: {username}\n'
                        f'Phone: {phone}'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating admin: {str(e)}')
            )