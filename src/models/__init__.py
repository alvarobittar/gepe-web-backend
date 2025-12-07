# Importar todos los modelos para que Alembic pueda detectarlos
from .user import User
from .club import Club
from .product import Product, Category, ProductSizeStock
from .product_price_settings import ProductPriceSettings
from .cart import CartItem
from .order import Order, OrderItem
from .payment import Payment
from .promo_banner import PromoBanner
from .promo_banner_settings import PromoBannerSettings

__all__ = [
    "User",
    "Club",
    "Product",
    "Category",
    "ProductSizeStock",
    "ProductPriceSettings",
    "CartItem",
    "Order",
    "OrderItem",
    "Payment",
    "PromoBanner",
    "PromoBannerSettings",
]

