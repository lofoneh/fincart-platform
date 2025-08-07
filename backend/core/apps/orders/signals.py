from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Order, OrderStatusHistory
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Order)
def update_order_timestamps(sender, instance, **kwargs):
    """Update timestamps when order status changes"""
    if instance.pk:  # Only for existing orders
        try:
            old_order = Order.objects.get(pk=instance.pk)
            
            # Update timestamps based on status changes
            if old_order.status != instance.status:
                now = timezone.now()
                
                if instance.status == 'confirmed' and not instance.confirmed_at:
                    instance.confirmed_at = now
                elif instance.status == 'shipped' and not instance.shipped_at:
                    instance.shipped_at = now
                elif instance.status == 'delivered' and not instance.delivered_at:
                    instance.delivered_at = now
                elif instance.status == 'cancelled' and not instance.cancelled_at:
                    instance.cancelled_at = now
                    
        except Order.DoesNotExist:
            pass


@receiver(post_save, sender=Order)
def create_initial_status_history(sender, instance, created, **kwargs):
    """Create initial status history when order is created"""
    if created:
        OrderStatusHistory.objects.create(
            order=instance,
            status=instance.status,
            notes='Order created',
            created_by=None  # System created
        )
        
        logger.info(f"Order {instance.order_number} created with initial status {instance.status}")


@receiver(post_save, sender=Order)
def log_status_changes(sender, instance, created, **kwargs):
    """Log order status changes"""
    if not created and instance.pk:
        try:
            # Get the previous status from database
            current_order = Order.objects.get(pk=instance.pk)
            
            # This will be called after save, so we need to track changes differently
            # You might want to implement a custom change tracking mechanism
            logger.info(f"Order {instance.order_number} status updated to {instance.status}")
            
        except Order.DoesNotExist:
            pass


# Optional: Add signals for inventory management
@receiver(post_save, sender=Order)
def handle_inventory_on_order_confirm(sender, instance, **kwargs):
    """Handle inventory deduction when order is confirmed"""
    if instance.status == 'confirmed' and instance.payment_status == 'paid':
        # Implement inventory deduction logic here
        # This would integrate with your products app inventory system
        
        for item in instance.items.all():
            # Example: Reduce product stock
            # item.product.reduce_stock(item.quantity)
            # if item.variant:
            #     item.variant.reduce_stock(item.quantity)
            pass
        
        logger.info(f"Inventory processed for order {instance.order_number}")


@receiver(post_save, sender=Order)
def handle_inventory_on_order_cancel(sender, instance, **kwargs):
    """Handle inventory restoration when order is cancelled"""
    if instance.status == 'cancelled':
        # Implement inventory restoration logic here
        
        for item in instance.items.all():
            # Example: Restore product stock
            # item.product.restore_stock(item.quantity)
            # if item.variant:
            #     item.variant.restore_stock(item.quantity)
            pass
        
        logger.info(f"Inventory restored for cancelled order {instance.order_number}")