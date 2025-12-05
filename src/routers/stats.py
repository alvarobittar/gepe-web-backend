from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

from ..database import get_db
from ..models.product import Product, Category
from ..models.promo_banner import PromoBanner
from ..models.order import Order, OrderItem
from ..models.user import User

router = APIRouter(prefix="/stats", tags=["stats"])


# --- Schemas para Dashboard ---

class TopProductStats(BaseModel):
    name: str
    category: Optional[str] = None
    total_quantity: int
    stock: int
    price: float


class RecentOrderStats(BaseModel):
    order_number: str
    customer_name: str
    customer_initials: str
    product_name: str
    amount: float
    status: str
    date: str


class SalesDataPoint(BaseModel):
    date: str
    revenue: float


class DashboardStatsResponse(BaseModel):
    products: int
    categories: int
    promo_banners: int
    total_revenue: float
    active_orders: int
    new_customers: int
    top_products: List[TopProductStats]
    recent_orders: List[RecentOrderStats]
    sales_chart: List[SalesDataPoint]


@router.get("/ranking")
async def get_ranking():
    # Placeholder ranking; would call services.ranking_service in real app
    return {
        "ranking": [
            {"product_id": 2, "score": 91},
            {"product_id": 1, "score": 75},
        ]
    }


def get_customer_initials(name: str) -> str:
    """Genera iniciales del nombre del cliente (ej: 'Santiago Paez' -> 'SP')"""
    if not name:
        return "??"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif len(parts) == 1:
        return parts[0][:2].upper()
    return "??"


def format_relative_date(dt: datetime) -> str:
    """Formatea una fecha como tiempo relativo (ej: 'Hace 2 min', 'Ayer')"""
    if not dt:
        return "Desconocido"
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days == 0:
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if hours == 0:
            if minutes <= 1:
                return "Hace 1 min"
            return f"Hace {minutes} min"
        elif hours == 1:
            return "Hace 1 hora"
        else:
            return f"Hace {hours} horas"
    elif diff.days == 1:
        return "Ayer"
    elif diff.days < 7:
        return f"Hace {diff.days} días"
    else:
        return dt.strftime("%d/%m/%Y")


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Endpoint para obtener estadísticas completas del dashboard de administración.
    Incluye ingresos, pedidos, clientes, productos top, pedidos recientes y gráfico de ventas.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # --- Estadísticas básicas ---
        products_count = db.query(func.count(Product.id)).scalar() or 0
        categories_count = db.query(func.count(Category.id)).scalar() or 0
        promo_banners_count = db.query(func.count(PromoBanner.id)).scalar() or 0
        
        # --- Ingresos totales (solo pedidos PAID) ---
        try:
            total_revenue = db.query(func.sum(Order.total_amount)).filter(
                Order.status == "PAID"
            ).scalar() or 0.0
        except Exception as e:
            logger.warning(f"Error al calcular ingresos: {e}")
            total_revenue = 0.0
        
        # --- Pedidos activos (no cancelados ni reembolsados) ---
        try:
            active_orders = db.query(func.count(Order.id)).filter(
                ~Order.status.in_(["CANCELLED", "REFUNDED"])
            ).scalar() or 0
        except Exception as e:
            logger.warning(f"Error al contar pedidos activos: {e}")
            active_orders = db.query(func.count(Order.id)).scalar() or 0
        
        # --- Clientes nuevos (últimos 30 días) ---
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        try:
            new_customers = db.query(func.count(User.id)).filter(
                User.created_at >= thirty_days_ago
            ).scalar() or 0
        except Exception as e:
            logger.warning(f"Error al contar clientes nuevos: {e}")
            # Si la columna created_at no existe, contar todos los usuarios
            new_customers = db.query(func.count(User.id)).scalar() or 0
        
        # --- Top productos vendidos (basado en OrderItems de pedidos PAID) ---
        top_products = []
        try:
            top_products_query = (
                db.query(
                    OrderItem.product_name,
                    OrderItem.product_id,
                    func.sum(OrderItem.quantity).label("total_quantity")
                )
                .join(Order, OrderItem.order_id == Order.id)
                .filter(Order.status == "PAID")
                .group_by(OrderItem.product_name, OrderItem.product_id)
                .order_by(desc("total_quantity"))
                .limit(4)
                .all()
            )
            
            for item in top_products_query:
                # Buscar info del producto original si existe
                product = None
                if item.product_id:
                    product = db.query(Product).filter(Product.id == item.product_id).first()
                
                category_name = None
                stock = 0
                price = 0.0
                
                if product:
                    if product.category:
                        category_name = product.category.name
                    stock = product.stock or 0
                    price = product.price or 0.0
                
                top_products.append(TopProductStats(
                    name=item.product_name,
                    category=category_name,
                    total_quantity=item.total_quantity,
                    stock=stock,
                    price=price
                ))
        except Exception as e:
            logger.warning(f"Error al obtener top productos: {e}")
        
        # --- Pedidos recientes (últimos 5) ---
        recent_orders = []
        try:
            recent_orders_query = (
                db.query(Order)
                .order_by(desc(Order.created_at))
                .limit(5)
                .all()
            )
            
            for order in recent_orders_query:
                # Obtener el nombre del primer producto
                first_item = db.query(OrderItem).filter(OrderItem.order_id == order.id).first()
                product_name = first_item.product_name if first_item else "Sin productos"
                
                # Si hay más de un item, agregar indicador
                items_count = db.query(func.count(OrderItem.id)).filter(OrderItem.order_id == order.id).scalar() or 0
                if items_count > 1:
                    product_name += f" (+{items_count - 1})"
                
                recent_orders.append(RecentOrderStats(
                    order_number=order.order_number or f"#ORD-{order.id}",
                    customer_name=order.customer_name or "Cliente",
                    customer_initials=get_customer_initials(order.customer_name),
                    product_name=product_name,
                    amount=order.total_amount or 0.0,
                    status=order.status or "PENDING",
                    date=format_relative_date(order.created_at)
                ))
        except Exception as e:
            logger.warning(f"Error al obtener pedidos recientes: {e}")
        
        # --- Datos para gráfico de ventas (últimos 30 días) ---
        sales_chart = []
        try:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            for i in range(30, -1, -1):
                day = today - timedelta(days=i)
                next_day = day + timedelta(days=1)
                
                daily_revenue = db.query(func.sum(Order.total_amount)).filter(
                    Order.status == "PAID",
                    Order.created_at >= day,
                    Order.created_at < next_day
                ).scalar() or 0.0
                
                sales_chart.append(SalesDataPoint(
                    date=day.strftime("%Y-%m-%d"),
                    revenue=daily_revenue
                ))
        except Exception as e:
            logger.warning(f"Error al calcular gráfico de ventas: {e}")
            # Generar datos vacíos
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            for i in range(30, -1, -1):
                day = today - timedelta(days=i)
                sales_chart.append(SalesDataPoint(
                    date=day.strftime("%Y-%m-%d"),
                    revenue=0.0
                ))
        
        return DashboardStatsResponse(
            products=products_count,
            categories=categories_count,
            promo_banners=promo_banners_count,
            total_revenue=total_revenue,
            active_orders=active_orders,
            new_customers=new_customers,
            top_products=top_products,
            recent_orders=recent_orders,
            sales_chart=sales_chart
        )
    
    except Exception as e:
        logger.error(f"Error crítico en dashboard stats: {e}", exc_info=True)
        # Retornar respuesta vacía en caso de error crítico
        return DashboardStatsResponse(
            products=0,
            categories=0,
            promo_banners=0,
            total_revenue=0.0,
            active_orders=0,
            new_customers=0,
            top_products=[],
            recent_orders=[],
            sales_chart=[]
        )

