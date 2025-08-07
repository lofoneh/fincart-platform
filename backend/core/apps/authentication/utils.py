# apps/authentication/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import requests
import logging

logger = logging.getLogger(__name__)


def send_verification_email(user, token):
    """Send email verification email to user"""
    try:
        subject = 'Verify Your Email Address'
        
        # Create verification URL
        verification_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}"
        
        # Create email context
        context = {
            'user': user,
            'verification_url': verification_url,
            'site_name': getattr(settings, 'SITE_NAME', 'FinCart'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@fincart.com')
        }
        
        # Render email templates
        html_message = render_to_string('emails/verify_email.html', context)
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        
        # Send email
        send_mail(
            subject,
            plain_message,
            from_email,
            [user.email],
            html_message=html_message,
        )
        logger.info(f"Verification email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {e}")
        raise Exception("Failed to send verification email")
    
def send_password_reset_email(user, token):
    """Send password reset email to user"""
    try:
        subject = 'Reset Your Password'
        # Create reset URL
        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        # Create email context
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': getattr(settings, 'SITE_NAME', 'FinCart'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'support@fincart.com')
        }
        # Render email templates
        html_message = render_to_string('emails/reset_password.html', context)
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        # Send email
        send_mail(
            subject,
            plain_message,
            from_email,
            [user.email],
            html_message=html_message,
        )
        logger.info(f"Password reset email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {e}")
        raise Exception("Failed to send password reset email")
    
    
def send_sms_code(phone_number, code):
    """Send SMS verification code to user's phone number"""
    try:
        api_url = f"{settings.SMS_API_URL}/send"
        payload = {
            'phone_number': phone_number,
            'message': f"Your verification code is: {code}"
        }
        headers = {
            'Authorization': f"Bearer {settings.SMS_API_KEY}",
            'Content-Type': 'application/json'
        }
        response = requests.post(api_url, json=payload, headers=headers)
        if response.status_code == 200:
            logger.info(f"SMS sent to {phone_number}")
        else:
            logger.error(f"Failed to send SMS to {phone_number}: {response.text}")
            raise Exception("Failed to send SMS")
    except Exception as e:
        logger.error(f"Error sending SMS to {phone_number}: {e}")
        raise Exception("Failed to send SMS")