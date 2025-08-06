from rest_framework import generics, viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from .models import Product, Category, ProductImage, ProductVariant
from .serializers import (
    ProductSerializer, ProductDetailSerializer, CategorySerializer,
    ProductImageSerializer, ProductVariantSerializer,
    ProductCreateSerializer, ProductUpdateSerializer
)
from .filters import ProductFilter
from .permissions import IsSellerOrReadOnly, IsOwnerOrReadOnly


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for categories with read-only access.
    Supports slug-based lookup and product listing per category.
    """
    queryset = Category.objects.filter(is_active=True).order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'
    search_fields = ['name', 'description']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        """Get all active products in this category with pagination."""
        category = self.get_object()
        products = Product.objects.filter(
            category=category,
            status='active'
        ).select_related('seller', 'category').prefetch_related('images')
        
        # Apply filtering if needed
        filter_backend = DjangoFilterBackend()
        products = filter_backend.filter_queryset(request, products, self)
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    """
    Complete CRUD ViewSet for products with advanced features.
    """
    serializer_class = ProductSerializer
    permission_classes = [IsSellerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'tags', 'short_description']
    ordering_fields = ['created_at', 'price', 'view_count', 'purchase_count', 'name']
    ordering = ['-created_at']
    lookup_field = 'slug'

    def get_queryset(self):
        """Return appropriate queryset based on action and user permissions."""
        base_queryset = Product.objects.select_related('seller', 'category').prefetch_related('images')
        
        if self.action in ['list', 'retrieve']:
            # Public actions - only show active products
            return base_queryset.filter(status='active')
        elif self.action in ['my_products']:
            # User's own products - show all statuses
            if self.request.user.is_authenticated:
                try:
                    from apps.sellers.models import SellerProfile
                    seller_profile = SellerProfile.objects.get(user=self.request.user)
                    return base_queryset.filter(seller=seller_profile)
                except SellerProfile.DoesNotExist:
                    return Product.objects.none()
        
        # Admin or owner actions - show all products
        return base_queryset

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return ProductCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProductUpdateSerializer
        elif self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        """Auto-assign seller profile and validate seller permissions."""
        try:
            from apps.sellers.models import SellerProfile
            seller_profile = SellerProfile.objects.get(user=self.request.user)
            
            # Check if user is actually a seller
            if not hasattr(self.request.user, 'is_seller') or not self.request.user.is_seller:
                raise ValidationError("Only verified sellers can create products.")
                
            serializer.save(seller=seller_profile)
        except SellerProfile.DoesNotExist:
            raise ValidationError("Seller profile not found. Please complete your seller registration.")

    def retrieve(self, request, *args, **kwargs):
        """Retrieve product with view count increment."""
        instance = self.get_object()
        
        # Increment view count atomically
        Product.objects.filter(id=instance.id).update(view_count=F('view_count') + 1)
        
        # Refresh instance to get updated view count
        instance.refresh_from_db(fields=['view_count'])
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_products(self, request):
        """Get current user's products with filtering and search."""
        if not hasattr(request.user, 'is_seller') or not request.user.is_seller:
            return Response(
                {'error': 'Only sellers can access this endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products."""
        queryset = self.get_queryset().filter(is_featured=True)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_featured(self, request, slug=None):
        """Toggle featured status - admin or product owner only."""
        product = self.get_object()
        
        # Permission check
        if not (request.user.is_staff or product.seller.user == request.user):
            return Response(
                {'error': 'You do not have permission to modify featured status'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        product.is_featured = not product.is_featured
        product.save(update_fields=['is_featured'])
        
        return Response({
            'message': f'Product {"featured" if product.is_featured else "unfeatured"} successfully',
            'is_featured': product.is_featured
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def update_stock(self, request, slug=None):
        """Update product stock quantity with automatic status management."""
        product = self.get_object()
        
        # Permission check
        if product.seller.user != request.user:
            return Response(
                {'error': 'You can only update your own products'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            new_stock = int(request.data.get('stock_quantity', 0))
            if new_stock < 0:
                raise ValueError("Stock quantity cannot be negative")
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid stock quantity. Must be a non-negative integer.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update stock
        old_stock = product.stock_quantity
        product.stock_quantity = new_stock
        
        # Auto-update status based on stock
        if new_stock == 0 and product.status == 'active':
            product.status = 'out_of_stock'
        elif old_stock == 0 and new_stock > 0 and product.status == 'out_of_stock':
            product.status = 'active'
        
        product.save(update_fields=['stock_quantity', 'status'])
        
        return Response({
            'message': 'Stock updated successfully',
            'stock_quantity': product.stock_quantity,
            'status': product.status,
            'low_stock_warning': new_stock <= product.low_stock_threshold
        })

    @action(detail=True, methods=['get'])
    def variants(self, request, slug=None):
        """Get all variants for a product."""
        product = self.get_object()
        variants = ProductVariant.objects.filter(product=product).order_by('name', 'value')
        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def images(self, request, slug=None):
        """Get all images for a product."""
        product = self.get_object()
        images = ProductImage.objects.filter(product=product).order_by('sort_order', 'created_at')
        serializer = ProductImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced search with multiple criteria."""
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response(
                {'error': 'Search query parameter "q" is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Multi-field search
        queryset = self.get_queryset().filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(tags__icontains=query) |
            Q(category__name__icontains=query)
        ).distinct()
        
        # Apply additional filters
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# Legacy APIViews (Keep if you prefer them over ViewSet actions)
class ProductSearchView(generics.ListAPIView):
    """Legacy search view - consider using ProductViewSet.search action instead."""
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'short_description', 'tags']
    ordering_fields = ['created_at', 'price', 'view_count', 'purchase_count']

    def get_queryset(self):
        queryset = Product.objects.filter(status='active').select_related('seller', 'category')
        
        query = self.request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(short_description__icontains=query) |
                Q(tags__icontains=query) |
                Q(category__name__icontains=query)
            ).distinct()
        
        return queryset


class FeaturedProductsView(generics.ListAPIView):
    """Legacy featured products view - consider using ProductViewSet.featured action instead."""
    queryset = Product.objects.filter(
        status='active', 
        is_featured=True
    ).select_related('seller', 'category').prefetch_related('images')
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'price', 'view_count']
    ordering = ['-created_at']


class ProductsByCategoryView(generics.ListAPIView):
    """Legacy category products view - consider using CategoryViewSet.products action instead."""
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ProductFilter
    ordering_fields = ['created_at', 'price', 'view_count', 'purchase_count']

    def get_queryset(self):
        category_slug = self.kwargs['category_slug']
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        
        return Product.objects.filter(
            category=category,
            status='active'
        ).select_related('seller', 'category').prefetch_related('images')


class SellerProductsView(generics.ListAPIView):
    """Legacy seller products view - consider using ProductViewSet.my_products action instead."""
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'price', 'stock_quantity', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        try:
            from apps.sellers.models import SellerProfile
            seller_profile = SellerProfile.objects.get(user=self.request.user)
            return Product.objects.filter(seller=seller_profile).select_related('category')
        except SellerProfile.DoesNotExist:
            return Product.objects.none()

    def list(self, request, *args, **kwargs):
        """Override to add seller permission check."""
        if not hasattr(request.user, 'is_seller') or not request.user.is_seller:
            return Response(
                {'error': 'Only sellers can access this endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().list(request, *args, **kwargs)