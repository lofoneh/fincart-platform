from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
import secrets
import string


class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(
        'authentication.User', 
        on_delete=models.CASCADE, 
        related_name='orders'
    )
    
    # Order details
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending', db_index=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending', db_index=True)
    
    # Pricing with proper validation
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    shipping_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    currency = models.CharField(max_length=3, default='GHS')
    
    # Shipping information
    shipping_address = models.ForeignKey(
        'authentication.Address', 
        on_delete=models.PROTECT,  # Changed from SET_NULL to PROTECT
        related_name='orders'
    )
    billing_address = models.ForeignKey(
        'authentication.Address',
        on_delete=models.PROTECT,
        related_name='billing_orders',
        null=True,
        blank=True
    )
    shipping_method = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    
    # Payment reference
    payment_reference = models.CharField(max_length=100, blank=True, db_index=True)
    payment_method = models.CharField(max_length=50, blank=True)
    
    # Notes
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders_order'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_status']),
        ]
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
    
    def __str__(self):
        return f"Order {self.order_number} - {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        
        # Update timestamps based on status changes
        if self.pk:
            old_order = Order.objects.get(pk=self.pk)
            if old_order.status != self.status:
                if self.status == 'confirmed' and not self.confirmed_at:
                    self.confirmed_at = timezone.now()
                elif self.status == 'shipped' and not self.shipped_at:
                    self.shipped_at = timezone.now()
                elif self.status == 'delivered' and not self.delivered_at:
                    self.delivered_at = timezone.now()
                elif self.status == 'cancelled' and not self.cancelled_at:
                    self.cancelled_at = timezone.now()
        
        super().save(*args, **kwargs)

    @classmethod
    def generate_order_number(cls):
        """Generate secure unique order number"""
        while True:
            # Use more secure random generation
            random_part = ''.join(secrets.choice(string.digits) for _ in range(8))
            order_number = f'FC{random_part}'
            
            if not cls.objects.filter(order_number=order_number).exists():
                return order_number

    def get_total_items(self):
        """Get total quantity of items in order"""
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'confirmed']

    def can_be_refunded(self):
        """Check if order can be refunded"""
        return self.payment_status == 'paid' and self.status not in ['cancelled', 'refunded']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    variant = models.ForeignKey(
        'products.ProductVariant', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='order_items'
    )
    seller = models.ForeignKey(
        'sellers.SellerProfile', 
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Product snapshot for historical data
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100, blank=True)
    variant_name = models.CharField(max_length=255, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders_orderitem'
        unique_together = [['order', 'product', 'variant']]
        indexes = [
            models.Index(fields=['order', 'seller']),
            models.Index(fields=['product']),
            models.Index(fields=['seller']),
        ]
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
    
    def __str__(self):
        variant_info = f" - {self.variant_name}" if self.variant_name else ""
        return f"{self.product_name}{variant_info} (Order: {self.order.order_number})"

    def save(self, *args, **kwargs):
        # Auto-calculate total price if not provided
        if not self.total_price:
            self.total_price = self.unit_price * self.quantity
        
        # Capture product snapshot
        if not self.product_name:
            self.product_name = self.product.name
        if not self.product_sku:
            self.product_sku = getattr(self.product, 'sku', str(self.product.id))
        if self.variant and not self.variant_name:
            self.variant_name = self.variant.name
            
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Order.ORDER_STATUS)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'authentication.User', 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='order_status_updates'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'orders_orderstatushistory'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'created_at']),
        ]
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
    
    def __str__(self):
        user_info = self.created_by.username if self.created_by else "System"
        return f"Status {self.status} for Order {self.order.order_number} by {user_info}"


class OrderRefund(models.Model):
    """Track refund information for orders"""
    REFUND_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=REFUND_STATUS, default='pending')
    refund_reference = models.CharField(max_length=100, blank=True)
    
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_refunds'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders_orderrefund'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refund {self.amount} for Order {self.order.order_number}"