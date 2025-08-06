from django.db.models import Q, F
from django_filters import rest_framework as filters
from .models import Product, Category


class ProductFilter(filters.FilterSet):
    """Comprehensive filter set for products with advanced filtering options."""
    
    # Basic text filters
    name = filters.CharFilter(lookup_expr='icontains', help_text="Filter by product name")
    description = filters.CharFilter(lookup_expr='icontains', help_text="Filter by description")
    tags = filters.CharFilter(lookup_expr='icontains', help_text="Filter by tags")
    sku = filters.CharFilter(lookup_expr='icontains', help_text="Filter by SKU")
    
    # Category filters
    category = filters.ModelChoiceFilter(
        queryset=Category.objects.filter(is_active=True),
        help_text="Filter by category ID"
    )
    category_slug = filters.CharFilter(
        field_name='category__slug',
        lookup_expr='exact',
        help_text="Filter by category slug"
    )
    category_name = filters.CharFilter(
        field_name='category__name',
        lookup_expr='icontains',
        help_text="Filter by category name"
    )
    
    # Price range filters
    price_min = filters.NumberFilter(
        field_name='price',
        lookup_expr='gte',
        help_text="Minimum price"
    )
    price_max = filters.NumberFilter(
        field_name='price',
        lookup_expr='lte',
        help_text="Maximum price"
    )
    price_range = filters.RangeFilter(
        field_name='price',
        help_text="Price range (min,max)"
    )
    
    # Discount filters
    on_sale = filters.BooleanFilter(
        method='filter_on_sale',
        help_text="Filter products on sale"
    )
    discount_min = filters.NumberFilter(
        method='filter_discount_min',
        help_text="Minimum discount percentage"
    )
    
    # Stock filters
    in_stock = filters.BooleanFilter(
        method='filter_in_stock',
        help_text="Filter by stock availability"
    )
    low_stock = filters.BooleanFilter(
        method='filter_low_stock',
        help_text="Filter low stock products"
    )
    stock_min = filters.NumberFilter(
        field_name='stock_quantity',
        lookup_expr='gte',
        help_text="Minimum stock quantity"
    )
    stock_max = filters.NumberFilter(
        field_name='stock_quantity',
        lookup_expr='lte',
        help_text="Maximum stock quantity"
    )
    
    # Status and feature filters
    status = filters.ChoiceFilter(
        choices=Product.PRODUCT_STATUS,
        help_text="Filter by product status"
    )
    is_featured = filters.BooleanFilter(
        help_text="Filter featured products"
    )
    is_digital = filters.BooleanFilter(
        help_text="Filter digital products"
    )
    requires_shipping = filters.BooleanFilter(
        help_text="Filter products requiring shipping"
    )
    
    # Seller filters
    seller = filters.CharFilter(
        field_name='seller__user__username',
        lookup_expr='icontains',
        help_text="Filter by seller username"
    )
    seller_business = filters.CharFilter(
        field_name='seller__business_name',
        lookup_expr='icontains',
        help_text="Filter by seller business name"
    )
    seller_id = filters.UUIDFilter(
        field_name='seller__id',
        help_text="Filter by seller ID"
    )
    
    # Date filters
    created_after = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text="Filter products created after this date"
    )
    created_before = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text="Filter products created before this date"
    )
    updated_after = filters.DateTimeFilter(
        field_name='updated_at',
        lookup_expr='gte',
        help_text="Filter products updated after this date"
    )
    
    # Analytics filters
    view_count_min = filters.NumberFilter(
        field_name='view_count',
        lookup_expr='gte',
        help_text="Minimum view count"
    )
    purchase_count_min = filters.NumberFilter(
        field_name='purchase_count',
        lookup_expr='gte',
        help_text="Minimum purchase count"
    )
    
    # Advanced search
    search = filters.CharFilter(
        method='filter_search',
        help_text="Search across multiple fields"
    )
    
    # Ordering
    ordering = filters.OrderingFilter(
        fields=(
            ('created_at', 'created_at'),
            ('updated_at', 'updated_at'),
            ('name', 'name'),
            ('price', 'price'),
            ('stock_quantity', 'stock_quantity'),
            ('view_count', 'view_count'),
            ('purchase_count', 'purchase_count'),
        ),
        field_labels={
            'created_at': 'Date Created',
            'updated_at': 'Date Updated',
            'name': 'Product Name',
            'price': 'Price',
            'stock_quantity': 'Stock Quantity',
            'view_count': 'View Count',
            'purchase_count': 'Purchase Count',
        }
    )

    class Meta:
        model = Product
        fields = []  # We define all fields manually above

    def filter_on_sale(self, queryset, name, value):
        """Filter products that are on sale (have compare_at_price > price)."""
        if value:
            return queryset.filter(
                compare_at_price__isnull=False,
                compare_at_price__gt=F('price')
            )
        else:
            return queryset.filter(
                Q(compare_at_price__isnull=True) |
                Q(compare_at_price__lte=F('price'))
            )

    def filter_discount_min(self, queryset, name, value):
        """Filter products with minimum discount percentage."""
        if value is None:
            return queryset
        
        # Calculate discount percentage: ((compare_at_price - price) / compare_at_price) * 100
        from django.db.models import Case, When, DecimalField, F
        
        return queryset.annotate(
            discount_percentage=Case(
                When(
                    compare_at_price__gt=F('price'),
                    then=((F('compare_at_price') - F('price')) / F('compare_at_price')) * 100
                ),
                default=0,
                output_field=DecimalField(max_digits=5, decimal_places=2)
            )
        ).filter(discount_percentage__gte=value)

    def filter_in_stock(self, queryset, name, value):
        """Filter products that are in stock."""
        if value:
            return queryset.filter(
                Q(track_inventory=False) |
                Q(track_inventory=True, stock_quantity__gt=0)
            )
        else:
            return queryset.filter(
                track_inventory=True,
                stock_quantity=0
            )

    def filter_low_stock(self, queryset, name, value):
        """Filter products with low stock."""
        if value:
            return queryset.filter(
                track_inventory=True,
                stock_quantity__lte=F('low_stock_threshold'),
                stock_quantity__gt=0
            )
        return queryset

    def filter_search(self, queryset, name, value):
        """Advanced search across multiple fields."""
        if not value:
            return queryset
        
        search_terms = value.split()
        q_objects = Q()
        
        for term in search_terms:
            q_objects |= (
                Q(name__icontains=term) |
                Q(description__icontains=term) |
                Q(short_description__icontains=term) |
                Q(tags__icontains=term) |
                Q(category__name__icontains=term) |
                Q(seller__business_name__icontains=term) |
                Q(sku__icontains=term)
            )
        
        return queryset.filter(q_objects).distinct()


class CategoryFilter(filters.FilterSet):
    """Filter set for categories."""
    
    name = filters.CharFilter(lookup_expr='icontains')
    parent = filters.ModelChoiceFilter(
        queryset=Category.objects.filter(is_active=True)
    )
    has_parent = filters.BooleanFilter(
        method='filter_has_parent',
        help_text="Filter categories with/without parent"
    )
    is_active = filters.BooleanFilter()
    
    # Date filters
    created_after = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Product count filters
    min_products = filters.NumberFilter(
        method='filter_min_products',
        help_text="Minimum number of active products"
    )
    max_products = filters.NumberFilter(
        method='filter_max_products',
        help_text="Maximum number of active products"
    )

    class Meta:
        model = Category
        fields = ['is_active']

    def filter_has_parent(self, queryset, name, value):
        """Filter categories with or without parent."""
        if value:
            return queryset.filter(parent__isnull=False)
        else:
            return queryset.filter(parent__isnull=True)

    def filter_min_products(self, queryset, name, value):
        """Filter categories with minimum number of active products."""
        if value is None:
            return queryset
        
        from django.db.models import Count
        return queryset.annotate(
            active_products_count=Count('products', filter=Q(products__status='active'))
        ).filter(active_products_count__gte=value)

    def filter_max_products(self, queryset, name, value):
        """Filter categories with maximum number of active products."""
        if value is None:
            return queryset
        
        from django.db.models import Count
        return queryset.annotate(
            active_products_count=Count('products', filter=Q(products__status='active'))
        ).filter(active_products_count__lte=value)