from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from django.utils.safestring import mark_safe
from .models import Category, Product, ProductImage, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin configuration for Category model."""
    list_display = [
        'name', 'slug', 'parent', 'products_count', 'is_active', 
        'sort_order', 'created_at'
    ]
    list_filter = ['is_active', 'parent', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['sort_order', 'name']
    list_editable = ['is_active', 'sort_order']
    readonly_fields = ['created_at', 'updated_at', 'products_count']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'parent', 'description')
        }),
        ('Display', {
            'fields': ('image', 'is_active', 'sort_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('products_count',),
            'classes': ('collapse',)
        }),
    )

    def products_count(self, obj):
        """Display count of active products in category."""
        count = obj.products.filter(status='active').count()
        url = reverse('admin:products_product_changelist') + f'?category={obj.id}'
        return format_html('<a href="{}">{} products</a>', url, count)
    products_count.short_description = 'Active Products'

    def get_queryset(self, request):
        """Optimize queryset with product counts."""
        queryset = super().get_queryset(request)
        return queryset.annotate(
            active_products_count=Count('products', filter=Q(products__status='active'))
        )


class ProductImageInline(admin.TabularInline):
    """Inline admin for product images."""
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'sort_order']
    readonly_fields = ['image_preview']
    
    def image_preview(self, obj):
        """Display image preview."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Preview'


class ProductVariantInline(admin.TabularInline):
    """Inline admin for product variants."""
    model = ProductVariant
    extra = 0
    fields = [
        'name', 'value', 'price_adjustment', 'stock_quantity', 
        'sku', 'is_active'
    ]
    readonly_fields = ['sku']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin configuration for Product model."""
    list_display = [
        'name', 'seller_name', 'category', 'price', 'stock_info',
        'status', 'is_featured', 'view_count', 'created_at'
    ]
    list_filter = [
        'status', 'is_featured', 'is_digital', 'category', 'created_at',
        'seller__business_name', 'currency'
    ]
    search_fields = [
        'name', 'description', 'sku', 'seller__business_name',
        'seller__user__username'
    ]
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['-created_at']
    list_editable = ['status', 'is_featured']
    readonly_fields = [
        'id', 'slug', 'sku', 'view_count', 'purchase_count',
        'wishlist_count', 'created_at', 'updated_at', 'discount_info',
        'stock_status', 'profit_margin'
    ]
    inlines = [ProductImageInline, ProductVariantInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'seller', 'category', 'description', 'short_description')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_at_price', 'cost_price', 'currency', 'discount_info', 'profit_margin')
        }),
        ('Inventory', {
            'fields': ('stock_quantity', 'low_stock_threshold', 'track_inventory', 'sku', 'stock_status')
        }),
        ('Physical Attributes', {
            'fields': ('weight', 'length', 'width', 'height'),
            'classes': ('collapse',)
        }),
        ('SEO & Marketing', {
            'fields': ('meta_title', 'meta_description', 'tags', 'is_featured', 'is_digital', 'requires_shipping')
        }),
        ('Status', {
            'fields': ('status',)
        }),
        ('Analytics', {
            'fields': ('view_count', 'purchase_count', 'wishlist_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_featured', 'unmark_as_featured', 'mark_as_active',
        'mark_as_inactive', 'mark_as_draft'
    ]

    def seller_name(self, obj):
        """Display seller business name with link."""
        url = reverse('admin:sellers_sellerprofile_change', args=[obj.seller.pk])
        return format_html('<a href="{}">{}</a>', url, obj.seller.business_name)
    seller_name.short_description = 'Seller'
    seller_name.admin_order_field = 'seller__business_name'

    def stock_info(self, obj):
        """Display stock information with status."""
        if not obj.track_inventory:
            return mark_safe('<span style="color: blue;">Not tracked</span>')
        
        if obj.stock_quantity == 0:
            color = 'red'
            status = 'Out of stock'
        elif obj.is_low_stock:
            color = 'orange'
            status = f'Low stock ({obj.stock_quantity})'
        else:
            color = 'green'
            status = f'In stock ({obj.stock_quantity})'
        
        return mark_safe(f'<span style="color: {color};">{status}</span>')
    stock_info.short_description = 'Stock'

    def discount_info(self, obj):
        """Display discount information."""
        if obj.is_on_sale:
            return f"{obj.discount_percentage}% off (Save {obj.currency} {obj.compare_at_price - obj.price})"
        return "No discount"
    discount_info.short_description = 'Discount'

    def stock_status(self, obj):
        """Display detailed stock status."""
        if not obj.track_inventory:
            return "Inventory not tracked"
        
        status = f"Current: {obj.stock_quantity}"
        if obj.is_low_stock:
            status += f" (Below threshold of {obj.low_stock_threshold})"
        return status
    stock_status.short_description = 'Stock Status'

    def profit_margin(self, obj):
        """Calculate and display profit margin."""
        if obj.cost_price:
            margin = obj.price - obj.cost_price
            margin_percent = (margin / obj.price) * 100
            return f"{obj.currency} {margin} ({margin_percent:.1f}%)"
        return "Cost price not set"
    profit_margin.short_description = 'Profit Margin'

    # Admin actions
    def mark_as_featured(self, request, queryset):
        """Mark selected products as featured."""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} products marked as featured.')
    mark_as_featured.short_description = 'Mark selected products as featured'

    def unmark_as_featured(self, request, queryset):
        """Remove featured status from selected products."""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} products removed from featured.')
    unmark_as_featured.short_description = 'Remove featured status'

    def mark_as_active(self, request, queryset):
        """Mark selected products as active."""
        updated = queryset.update(status='active')
        self.message_user(request, f'{updated} products marked as active.')
    mark_as_active.short_description = 'Mark as active'

    def mark_as_inactive(self, request, queryset):
        """Mark selected products as inactive."""
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} products marked as inactive.')
    mark_as_inactive.short_description = 'Mark as inactive'

    def mark_as_draft(self, request, queryset):
        """Mark selected products as draft."""
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} products marked as draft.')
    mark_as_draft.short_description = 'Mark as draft'

    def get_queryset(self, request):
        """Optimize queryset."""
        queryset = super().get_queryset(request)
        return queryset.select_related('seller', 'category')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Admin configuration for ProductImage model."""
    list_display = [
        'product_name', 'image_preview', 'alt_text', 'is_primary',
        'sort_order', 'created_at'
    ]
    list_filter = ['is_primary', 'created_at']
    search_fields = ['product__name', 'alt_text']
    ordering = ['product', 'sort_order']
    list_editable = ['is_primary', 'sort_order']
    readonly_fields = ['created_at', 'image_preview']

    def product_name(self, obj):
        """Display product name with link."""
        url = reverse('admin:products_product_change', args=[obj.product.pk])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_name.short_description = 'Product'

    def image_preview(self, obj):
        """Display image preview."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 100px; max-width: 150px;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Preview'

    def get_queryset(self, request):
        """Optimize queryset."""
        queryset = super().get_queryset(request)
        return queryset.select_related('product')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Admin configuration for ProductVariant model."""
    list_display = [
        'product_name', 'name', 'value', 'final_price',
        'stock_quantity', 'sku', 'is_active'
    ]
    list_filter = ['name', 'is_active', 'created_at']
    search_fields = ['product__name', 'name', 'value', 'sku']
    ordering = ['product', 'name', 'value']
    list_editable = ['stock_quantity', 'is_active']
    readonly_fields = ['sku', 'final_price', 'created_at']

    fieldsets = (
        (None, {
            'fields': ('product', 'name', 'value', 'sku')
        }),
        ('Pricing', {
            'fields': ('price_adjustment', 'final_price')
        }),
        ('Inventory', {
            'fields': ('stock_quantity', 'is_active')
        }),
        ('Physical', {
            'fields': ('weight_adjustment',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def product_name(self, obj):
        """Display product name with link."""
        url = reverse('admin:products_product_change', args=[obj.product.pk])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_name.short_description = 'Product'

    def get_queryset(self, request):
        """Optimize queryset."""
        queryset = super().get_queryset(request)
        return queryset.select_related('product')


# Admin site customizations
admin.site.site_header = "FinCart Products Administration"
admin.site.site_title = "FinCart Products Admin"
admin.site.index_title = "Welcome to FinCart Products Administration"