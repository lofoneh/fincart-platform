from django.db import models
from apps.authentication.models import User

class SellerProfile(models.Model):
    APPROVAL_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=255)
    business_description = models.TextField()
    business_address = models.TextField()
    business_phone = models.CharField(max_length=20)
    business_email = models.EmailField()
    business_registration_number = models.CharField(max_length=50, null=True, blank=True)
    tax_identification_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Verification documents
    business_license = models.FileField(upload_to='seller_docs/', null=True, blank=True)
    tax_certificate = models.FileField(upload_to='seller_docs/', null=True, blank=True)
    identity_document = models.FileField(upload_to='seller_docs/', null=True, blank=True)
    
    # Status and metrics
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default='pending')
    approval_date = models.DateTimeField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_orders = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.business_name

    class Meta:
        verbose_name_plural = "Seller Profiles"
        ordering = ['-created_at']

class SellerBankAccount(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=255)
    branch_code = models.CharField(max_length=20, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_name} ({'Primary' if self.is_primary else 'Secondary'})"