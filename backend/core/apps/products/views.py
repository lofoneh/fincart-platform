from rest_framework import generics, viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, F
from django.shortcuts import get_object_or_404

from .models import Product, Category, ProductImage, ProductVariant
from .serializers import (
    ProductSerializer, ProductDetailSerializer, CategorySerializer,
    ProductImageSerializer, ProductVariantSerializer,
    ProductCreateSerializer, ProductUpdateSerializer
)
from .filters import ProductFilter
from .permissions import IsSellerOrReadOnly, IsOwnerOrReadOnly

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'slug'

    @action(detail=True, methods=['get'])
    def products(self, request, slug=None):
        category = self.get_object()
        products = Product.objects.filter(
            category=category,
            status='active'
        ).select_related('seller', 'category')
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsSellerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['created_at', 'price', 'view_count', 'purchase_count']
    ordering = ['-created_at']
    lookup_field = 'slug'

    def get_queryset(self):
        if self.action in ['list', 'retrieve']:
            return Product.objects.filter(status='active').select_related('seller', 'category')
        return Product.objects.all().select_related('seller', 'category')

    def get_serializer_class(self):
        if self.action == 'create':
            return ProductCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProductUpdateSerializer
        elif self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        # Auto-assign seller profile
        from apps.sellers.models import SellerProfile
        seller_profile = get_object_or_404(SellerProfile, user=self.request.user)
        serializer.save(seller=seller_profile)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Increment view count
        Product.objects.filter(id=instance.id).update(view_count=F('view_count') + 1)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def toggle_featured(self, request, slug=None):
        product = self.get_object()
        
        # Only admins or product owner can feature/unfeature
        if not (request.user.is_staff or product.seller.user == request.user):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        product.is_featured = not product.is_featured
        product.save()
        
        return Response({
            'message': f'Product {"featured" if product.is_featured else "unfeatured"} successfully',
            'is_featured': product.is_featured
        })

    @action(detail=True, methods=['post'])
    def update_stock(self, request, slug=None):
        product = self.get_object()
        
        if product.seller.user != request.user:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_stock = request.data.get('stock_quantity')
        if new_stock is None or new_stock < 0:
            return Response(
                {'error': 'Invalid stock quantity'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        product.stock_quantity = new_stock
        
        # Update status based on stock
        if new_stock == 0:
            product.status = 'out_of_stock'
        elif product.status == 'out_of_stock' and new_stock > 0:
            product.status = 'active'
        
        product.save()
        
        return Response({
            'message': 'Stock updated successfully',
            'stock_quantity': product.stock_quantity,
            'status': product.status
        })

    @action(detail=True, methods=['get'])
    def variants(self, request, slug=None):
        product = self.get_object()
        variants = ProductVariant.objects.filter(product=product)
        serializer = ProductVariantSerializer(variants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def images(self, request, slug=None):
        product = self.get_object()
        images = ProductImage.objects.filter(product=product).order_by('sort_order', 'created_at')
        serializer = ProductImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data)

class ProductSearchView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'short_description', 'tags']
    ordering_fields = ['created_at', 'price', 'view_count', 'purchase_count']

    def get_queryset(self):
        queryset = Product.objects.filter(status='active').select_related('seller', 'category')
        
        query = self.request.query_params.get('q', '')
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
    queryset = Product.objects.filter(status='active', is_featured=True).select_related('seller', 'category')
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

class ProductsByCategoryView(generics.ListAPIView):
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
        ).select_related('seller', 'category')

class SellerProductsView(generics.ListAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'price', 'stock_quantity', 'view_count']
    ordering = ['-created_at']

    def get_queryset(self):
        from apps.sellers.models import SellerProfile
        try:
            seller_profile = SellerProfile.objects.get(user=self.request.user)
            return Product.objects.filter(seller=seller_profile)
        except SellerProfile.DoesNotExist:
            return Product.objects.none()

    def get(self, request, *args, **kwargs):
        if not request.user.is_seller:
            return Response(
                {'error': 'Only sellers can access this endpoint'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().get(request, *args, **kwargs)