from rest_framework import serializers
from django.utils.text import slugify
from .models import Product, Category, ProductImage, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model with nested subcategories."""
    subcategories = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 'image',
            'is_active', 'sort_order', 'subcategories', 'products_count',
            'full_path', 'created_at'
        ]
        read_only_fields = ['slug', 'full_path', 'created_at']

    def get_subcategories(self, obj):
        """Get immediate subcategories (not recursive to avoid deep nesting)."""
        subcategories = obj.subcategories.filter(is_active=True)[:10]  # Limit for performance
        return CategorySerializer(subcategories, many=True, context=self.context).data

    def get_products_count(self, obj):
        """Get count of active products in this category."""
        return obj.products.filter(status='active').count()


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for Product Images."""
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = [
            'id', 'image', 'image_url', 'alt_text', 'is_primary', 
            'sort_order', 'created_at'
        ]

    def get_image_url(self, obj):
        """Get full image URL."""
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for Product Variants."""
    final_price = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'name', 'value', 'price_adjustment', 'final_price',
            'stock_quantity', 'is_in_stock', 'sku', 'weight_adjustment',
            'is_active', 'created_at'
        ]
        read_only_fields = ['sku', 'final_price', 'is_in_stock']


class ProductSerializer(serializers.ModelSerializer):
    """Main Product serializer for list views."""
    seller_name = serializers.CharField(source='seller.business_name', read_only=True)
    seller_username = serializers.CharField(source='seller.user.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    
    # Computed fields
    is_on_sale = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()
    
    # Related data
    primary_image = ProductImageSerializer(read_only=True)
    images_count = serializers.SerializerMethodField()
    variants_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'price', 
            'compare_at_price', 'currency', 'is_on_sale', 'discount_percentage',
            'stock_quantity', 'is_low_stock', 'is_in_stock', 'status',
            'is_featured', 'is_digital', 'view_count', 'purchase_count',
            'seller_name', 'seller_username', 'category_name', 'category_slug',
            'primary_image', 'images_count', 'variants_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'slug', 'view_count', 'purchase_count', 'is_on_sale',
            'discount_percentage', 'is_low_stock', 'is_in_stock'
        ]

    def get_images_count(self, obj):
        """Get total number of images."""
        return obj.images.count()

    def get_variants_count(self, obj):
        """Get total number of active variants."""
        return obj.variants.filter(is_active=True).count()


class ProductDetailSerializer(ProductSerializer):
    """Detailed Product serializer for single product views."""
    seller = serializers.SerializerMethodField()
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    tags_list = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + [
            'description', 'meta_title', 'meta_description', 'tags', 'tags_list',
            'weight', 'length', 'width', 'height', 'sku', 'low_stock_threshold',
            'track_inventory', 'requires_shipping', 'cost_price', 'wishlist_count',
            'seller', 'category', 'images', 'variants'
        ]

    def get_seller(self, obj):
        """Get basic seller information."""
        return {
            'id': obj.seller.id,
            'business_name': obj.seller.business_name,
            'username': obj.seller.user.username,
            'rating': getattr(obj.seller, 'rating', 0),
            'total_products': obj.seller.products.filter(status='active').count()
        }

    def get_tags_list(self, obj):
        """Convert comma-separated tags to list."""
        if obj.tags:
            return [tag.strip() for tag in obj.tags.split(',') if tag.strip()]
        return []


class ProductCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating products."""
    images = ProductImageSerializer(many=True, required=False)
    variants = ProductVariantSerializer(many=True, required=False)
    tags_list = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
        help_text="List of tags"
    )

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'short_description', 'category',
            'price', 'compare_at_price', 'cost_price', 'currency',
            'stock_quantity', 'low_stock_threshold', 'track_inventory',
            'weight', 'length', 'width', 'height', 'sku',
            'meta_title', 'meta_description', 'tags', 'tags_list',
            'is_featured', 'is_digital', 'requires_shipping', 'status',
            'images', 'variants'
        ]
        read_only_fields = ['slug']

    def validate_price(self, value):
        """Validate that price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate_compare_at_price(self, value):
        """Validate that compare_at_price is greater than price."""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Compare at price must be greater than 0.")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        price = attrs.get('price')
        compare_at_price = attrs.get('compare_at_price')
        
        if compare_at_price and price and compare_at_price <= price:
            raise serializers.ValidationError({
                'compare_at_price': 'Compare at price must be greater than the regular price.'
            })
        
        # Convert tags_list to tags string
        if 'tags_list' in attrs:
            tags_list = attrs.pop('tags_list')
            attrs['tags'] = ', '.join(tags_list)
        
        return attrs

    def create(self, validated_data):
        """Create product with related objects."""
        images_data = validated_data.pop('images', [])
        variants_data = validated_data.pop('variants', [])
        
        product = Product.objects.create(**validated_data)
        
        # Create images
        for image_data in images_data:
            ProductImage.objects.create(product=product, **image_data)
        
        # Create variants
        for variant_data in variants_data:
            ProductVariant.objects.create(product=product, **variant_data)
        
        return product


class ProductUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating products."""
    tags_list = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        write_only=True,
        help_text="List of tags"
    )

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'short_description', 'category',
            'price', 'compare_at_price', 'cost_price', 'currency',
            'stock_quantity', 'low_stock_threshold', 'track_inventory',
            'weight', 'length', 'width', 'height',
            'meta_title', 'meta_description', 'tags', 'tags_list',
            'is_featured', 'is_digital', 'requires_shipping', 'status'
        ]
        read_only_fields = ['slug', 'sku']

    def validate_price(self, value):
        """Validate that price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        price = attrs.get('price', self.instance.price if self.instance else None)
        compare_at_price = attrs.get('compare_at_price')
        
        if compare_at_price and price and compare_at_price <= price:
            raise serializers.ValidationError({
                'compare_at_price': 'Compare at price must be greater than the regular price.'
            })
        
        # Convert tags_list to tags string
        if 'tags_list' in attrs:
            tags_list = attrs.pop('tags_list')
            attrs['tags'] = ', '.join(tags_list)
        
        return attrs


class FeaturedProductSerializer(ProductSerializer):
    """Serializer for featured products with minimal data."""
    
    class Meta(ProductSerializer.Meta):
        fields = [
            'id', 'name', 'slug', 'short_description', 'price',
            'compare_at_price', 'currency', 'is_on_sale', 'discount_percentage',
            'seller_name', 'category_name', 'primary_image',
            'view_count', 'purchase_count', 'created_at'
        ]


class ProductSearchSerializer(ProductSerializer):
    """Serializer for search results with highlighted fields."""
    relevance_score = serializers.SerializerMethodField()
    
    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ['relevance_score']

    def get_relevance_score(self, obj):
        """Calculate relevance score based on search query matches."""
        query = self.context.get('search_query', '').lower()
        if not query:
            return 0
        
        score = 0
        # Name match (highest priority)
        if query in obj.name.lower():
            score += 10
        
        # Category match
        if obj.category and query in obj.category.name.lower():
            score += 5
        
        # Description match
        if query in obj.description.lower():
            score += 3
        
        # Tags match
        if obj.tags and query in obj.tags.lower():
            score += 2
        
        return score


class ProductQuickCreateSerializer(serializers.ModelSerializer):
    """Quick product creation with minimal fields for bulk operations."""
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 'price', 'stock_quantity',
            'status', 'tags'
        ]
        
    def validate_name(self, value):
        """Ensure product name is unique for this seller."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            seller_products = Product.objects.filter(
                seller__user=request.user,
                name__iexact=value
            )
            if self.instance:
                seller_products = seller_products.exclude(pk=self.instance.pk)
            
            if seller_products.exists():
                raise serializers.ValidationError(
                    "You already have a product with this name."
                )
        return value


class CategoryProductCountSerializer(serializers.ModelSerializer):
    """Category serializer with product counts for analytics."""
    active_products_count = serializers.SerializerMethodField()
    total_products_count = serializers.SerializerMethodField()
    featured_products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'active_products_count',
            'total_products_count', 'featured_products_count'
        ]
    
    def get_active_products_count(self, obj):
        return obj.products.filter(status='active').count()
    
    def get_total_products_count(self, obj):
        return obj.products.count()
    
    def get_featured_products_count(self, obj):
        return obj.products.filter(status='active', is_featured=True).count()