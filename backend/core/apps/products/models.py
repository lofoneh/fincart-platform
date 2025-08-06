from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from apps.sellers.models import SellerProfile
import uuid


class Category(models.Model):
    """Product categories with hierarchical structure."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, help_text="Auto-generated from name")
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='subcategories'
    )
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
            models.Index(fields=['parent']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name

    @property
    def full_path(self):
        """Get full category path for breadcrumbs."""
        path = [self.name]
        parent = self.parent
        while parent:
            path.insert(0, parent.name)
            parent = parent.parent
        return " > ".join(path)

    def get_all_products(self):
        """Get all products in this category and subcategories."""
        from django.db.models import Q
        categories = [self.id]
        
        def get_subcategory_ids(category):
            subcats = category.subcategories.values_list('id', flat=True)
            for subcat_id in subcats:
                categories.append(subcat_id)
                subcat = Category.objects.get(id=subcat_id)
                get_subcategory_ids(subcat)
        
        get_subcategory_ids(self)
        return Product.objects.filter(category_id__in=categories)


class Product(models.Model):
    """Main product model with comprehensive e-commerce features."""
    
    PRODUCT_STATUS = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
    ]
    
    CURRENCY_CHOICES = [
        ('GHS', 'Ghana Cedis'),
        ('USD', 'US Dollar'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.ForeignKey(
        SellerProfile, 
        on_delete=models.CASCADE, 
        related_name='products'
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='products'
    )
    
    # Basic info
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, help_text="Auto-generated from name")
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    
    # Pricing
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    compare_at_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Original price for showing discounts"
    )
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Cost price for profit calculation"
    )
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='GHS')
    
    # Inventory
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Alert threshold for low stock"
    )
    track_inventory = models.BooleanField(
        default=True,
        help_text="Whether to track inventory for this product"
    )
    sku = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True,
        help_text="Stock Keeping Unit"
    )
    
    # Physical attributes (for shipping calculations)
    weight = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        null=True, 
        blank=True,
        help_text="Weight in kg"
    )
    length = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Length in cm"
    )
    width = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Width in cm"
    )
    height = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Height in cm"
    )
    
    # SEO and metadata
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    tags = models.CharField(
        max_length=500, 
        blank=True,
        help_text="Comma-separated tags for search"
    )
    
    # Status and visibility
    status = models.CharField(
        max_length=20, 
        choices=PRODUCT_STATUS, 
        default='draft',
        db_index=True
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Show in featured products section"
    )
    is_digital = models.BooleanField(
        default=False,
        help_text="Digital products don't require shipping"
    )
    requires_shipping = models.BooleanField(default=True)
    
    # Analytics and performance
    view_count = models.PositiveIntegerField(default=0)
    purchase_count = models.PositiveIntegerField(default=0)
    wishlist_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['seller']),
            models.Index(fields=['category']),
            models.Index(fields=['price']),
            models.Index(fields=['created_at']),
            models.Index(fields=['view_count']),
            models.Index(fields=['purchase_count']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-generate slug and SKU if not provided."""
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        if not self.sku:
            # Generate SKU: SELLER_PREFIX + CATEGORY_PREFIX + RANDOM
            seller_prefix = self.seller.user.username[:3].upper()
            cat_prefix = self.category.name[:3].upper() if self.category else "GEN"
            self.sku = f"{seller_prefix}-{cat_prefix}-{str(self.id)[:8].upper()}"
        
        # Auto-update status based on stock
        if self.track_inventory and self.stock_quantity == 0 and self.status == 'active':
            self.status = 'out_of_stock'
        elif self.track_inventory and self.stock_quantity > 0 and self.status == 'out_of_stock':
            self.status = 'active'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} by {self.seller.business_name}"

    @property
    def is_on_sale(self):
        """Check if product has a discount."""
        return self.compare_at_price and self.compare_at_price > self.price

    @property
    def discount_percentage(self):
        """Calculate discount percentage."""
        if self.is_on_sale:
            return round(((self.compare_at_price - self.price) / self.compare_at_price) * 100)
        return 0

    @property
    def is_low_stock(self):
        """Check if product is low on stock."""
        return self.track_inventory and self.stock_quantity <= self.low_stock_threshold

    @property
    def is_in_stock(self):
        """Check if product is in stock."""
        return not self.track_inventory or self.stock_quantity > 0

    @property
    def primary_image(self):
        """Get the primary product image."""
        return self.images.filter(is_primary=True).first() or self.images.first()

    def get_absolute_url(self):
        """Get product detail URL."""
        return f"/products/{self.slug}/"


class ProductImage(models.Model):
    """Product images with support for multiple images per product."""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to='products/%Y/%m/')
    alt_text = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Alternative text for accessibility"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Main product image"
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['product', 'is_primary']),
            models.Index(fields=['product', 'sort_order']),
        ]
    
    def save(self, *args, **kwargs):
        """Ensure only one primary image per product."""
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product, 
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product.name} - Image {self.sort_order + 1}"


class ProductVariant(models.Model):
    """Product variants for different options like size, color, etc."""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name='variants'
    )
    name = models.CharField(
        max_length=100,
        help_text="Variant name (e.g., Size, Color)"
    )
    value = models.CharField(
        max_length=100,
        help_text="Variant value (e.g., Large, Red)"
    )
    price_adjustment = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="Price difference from base product"
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    sku = models.CharField(max_length=100, unique=True, blank=True)
    weight_adjustment = models.DecimalField(
        max_digits=8, 
        decimal_places=3, 
        default=0.00,
        help_text="Weight difference from base product"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('product', 'name', 'value')
        ordering = ['name', 'value']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['sku']),
        ]
    
    def save(self, *args, **kwargs):
        """Auto-generate SKU for variant."""
        if not self.sku:
            base_sku = f"{self.product.sku}-{self.name[:2].upper()}{self.value[:2].upper()}"
            sku = base_sku
            counter = 1
            while ProductVariant.objects.filter(sku=sku).exclude(pk=self.pk).exists():
                sku = f"{base_sku}-{counter}"
                counter += 1
            self.sku = sku
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"

    @property
    def final_price(self):
        """Calculate final price including adjustment."""
        return self.product.price + self.price_adjustment

    @property
    def is_in_stock(self):
        """Check if variant is in stock."""
        return self.stock_quantity > 0