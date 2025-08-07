from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Cart(models.Model):
    user = models.OneToOneField(
        'authentication.User', 
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_cart'
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'
    
    def __str__(self):
        return f"Cart for {self.user.email}"

    def get_total_items(self):
        """Get total quantity of items in cart"""
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    def get_total_price(self):
        """Get total price of all items in cart"""
        total = Decimal('0.00')
        for item in self.items.select_related('product', 'variant'):
            total += item.get_total_price()
        return total
    
    def get_unique_items_count(self):
        """Get count of unique items (not quantity)"""
        return self.items.count()
    
    def clear(self):
        """Clear all items from cart"""
        self.items.all().delete()
    
    def is_empty(self):
        """Check if cart is empty"""
        return not self.items.exists()


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, 
        on_delete=models.CASCADE, 
        related_name='items'
    )
    product = models.ForeignKey(
        'products.Product', 
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    variant = models.ForeignKey(
        'products.ProductVariant', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_cartitem'
        unique_together = [['cart', 'product', 'variant']]
        indexes = [
            models.Index(fields=['cart', 'created_at']),
            models.Index(fields=['product']),
        ]
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
    
    def __str__(self):
        variant_info = f" - {self.variant.name}" if self.variant else ""
        return f"{self.product.name}{variant_info} ({self.quantity}) - {self.cart.user.email}"

    def clean(self):
        """Validate cart item"""
        if self.variant and self.variant.product != self.product:
            raise ValidationError("Variant must belong to the selected product")
        
        # Check stock availability
        if hasattr(self.product, 'stock') and self.product.stock < self.quantity:
            raise ValidationError(f"Only {self.product.stock} items available in stock")
        
        if self.variant and hasattr(self.variant, 'stock') and self.variant.stock < self.quantity:
            raise ValidationError(f"Only {self.variant.stock} variant items available in stock")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_unit_price(self):
        """Get unit price including variant adjustment"""
        base_price = self.product.price
        if self.variant:
            base_price += self.variant.price_adjustment
        return base_price

    def get_total_price(self):
        """Get total price for this cart item"""
        return self.get_unit_price() * self.quantity
    
    def update_quantity(self, quantity):
        """Update quantity with validation"""
        if quantity <= 0:
            self.delete()
        else:
            self.quantity = quantity
            self.save()