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
from ..models.unique_visit import UniqueVisit

router = APIRouter(prefix="/stats", tags=["stats"])


# --- Schemas para Sales Ranking ---

class ProductSalesRanking(BaseModel):
    id: int
    name: str
    club_name: Optional[str] = None
    sales_count: int
    preview_image_url: Optional[str] = None
    slug: str


class SalesRankingResponse(BaseModel):
    ranking: List[ProductSalesRanking]


class TrendingParams(BaseModel):
    """
    Parámetros opcionales para el ranking de tendencias.
    - days: ventana de días hacia atrás a considerar (por defecto 7)
    - limit: cantidad máxima de productos a devolver (por defecto 10)
    """
    days: int = 7
    limit: int = 10


# --- Schemas para Dashboard ---

class TopProductStats(BaseModel):
    name: str
    category: Optional[str] = None
    total_quantity: int
    stock: int
    price: float
    total_revenue: float
    slug: Optional[str] = None


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
    unique_visitors: int  # Nuevo campo para visitantes únicos
    top_products: List[TopProductStats]
    recent_orders: List[RecentOrderStats]
    sales_chart: List[SalesDataPoint]
    # Nuevos bloques para gráficos del dashboard
    order_status: dict
    monthly_orders: List[dict]


@router.get("/ranking")
async def get_ranking():
    # Placeholder ranking; would call services.ranking_service in real app
    return {
        "ranking": [
            {"product_id": 2, "score": 91},
            {"product_id": 1, "score": 75},
        ]
    }


class UniqueVisitRequest(BaseModel):
    session_id: str


@router.post("/unique-visit")
async def track_unique_visit(
    request: UniqueVisitRequest,
    db: Session = Depends(get_db)
):
    """
    Registra una visita única.
    El frontend envía un session_id único por navegador (guardado en localStorage).
    Si ya existe, no se crea un nuevo registro.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Verificar si ya existe
        existing = db.query(UniqueVisit).filter(
            UniqueVisit.session_id == request.session_id
        ).first()
        
        if not existing:
            # Crear nuevo registro de visita
            new_visit = UniqueVisit(session_id=request.session_id)
            db.add(new_visit)
            db.commit()
            logger.info(f"Nueva visita única registrada: {request.session_id[:8]}...")
            return {"status": "ok", "message": "Nueva visita registrada"}
        
        return {"status": "ok", "message": "Visita ya registrada"}
    
    except Exception as e:
        logger.error(f"Error al registrar visita única: {e}")
        db.rollback()
        return {"status": "error", "message": str(e)}


@router.get("/sales-ranking", response_model=SalesRankingResponse)
def get_sales_ranking(db: Session = Depends(get_db)):
    """
    Obtiene el ranking de ventas de todos los productos.
    - Cuenta las unidades vendidas de pedidos (excluyendo CANCELLED y REFUNDED)
    - Suma el ajuste manual de ventas (ventas de tienda física)
    - Ordena por cantidad vendida total (descendente)
    - Para productos con 0 ventas, ordena alfabéticamente por nombre del club
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Subconsulta para obtener total vendido por producto (ventas online)
        # Contar todos los pedidos EXCEPTO los cancelados/reembolsados/carritos abandonados
        EXCLUDED_STATUSES = ["CANCELLED", "REFUNDED", "CART"]
        sales_subquery = (
            db.query(
                OrderItem.product_id,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("sold_qty")
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(~Order.status.in_(EXCLUDED_STATUSES))
            .group_by(OrderItem.product_id)
            .subquery()
        )
        
        # Consulta principal: todos los productos activos con sus ventas
        # total_sales = ventas_online + ajuste_manual
        products_with_sales = (
            db.query(
                Product.id,
                Product.name,
                Product.club_name,
                Product.preview_image_url,
                Product.slug,
                Product.manual_sales_adjustment,
                func.coalesce(sales_subquery.c.sold_qty, 0).label("online_sales")
            )
            .outerjoin(sales_subquery, Product.id == sales_subquery.c.product_id)
            .filter(Product.is_active == True)
            .all()
        )
        
        # Calcular total y ordenar en Python para sumar el ajuste manual
        ranking = []
        for p in products_with_sales:
            online_sales = p.online_sales or 0
            manual_adjustment = p.manual_sales_adjustment or 0
            total_sales = online_sales + manual_adjustment
            
            ranking.append(ProductSalesRanking(
                id=p.id,
                name=p.name,
                club_name=p.club_name,
                sales_count=total_sales,
                preview_image_url=p.preview_image_url,
                slug=p.slug
            ))
        
        # Ordenar: mayor venta primero, luego alfabético como desempate
        ranking.sort(key=lambda x: (-x.sales_count, x.club_name or x.name or ""))
        
        return SalesRankingResponse(ranking=ranking)
        
    except Exception as e:
        logger.error(f"Error al obtener ranking de ventas: {e}", exc_info=True)
        return SalesRankingResponse(ranking=[])


@router.get("/trending-ranking", response_model=SalesRankingResponse)
def get_trending_ranking(
    days: int = 7,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """
    Obtiene el ranking de productos en **tendencia**.

    - Considera solo las unidades vendidas en pedidos dentro de los últimos `days` días (excluyendo CANCELLED y REFUNDED).
    - Suma el ajuste manual de ventas (ventas de tienda física)
    - Ordena por cantidad vendida total en esa ventana de tiempo (descendente).
    - Devuelve como máximo `limit` productos (por defecto Top 10).
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Fecha límite: hoy - N días
        now_utc = datetime.utcnow()
        from_date = now_utc - timedelta(days=days if days > 0 else 7)

        # Subconsulta: ventas por producto en la ventana de tiempo (ventas online)
        # Contar todos los pedidos EXCEPTO los cancelados/reembolsados/carritos abandonados
        EXCLUDED_STATUSES = ["CANCELLED", "REFUNDED", "CART"]
        weekly_sales_subquery = (
            db.query(
                OrderItem.product_id,
                func.coalesce(func.sum(OrderItem.quantity), 0).label("sold_qty_week"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                ~Order.status.in_(EXCLUDED_STATUSES),
                Order.created_at >= from_date,
            )
            .group_by(OrderItem.product_id)
            .subquery()
        )

        # Consulta principal: productos activos con ventas de la semana
        products_with_weekly_sales = (
            db.query(
                Product.id,
                Product.name,
                Product.club_name,
                Product.preview_image_url,
                Product.slug,
                Product.manual_sales_adjustment,
                func.coalesce(weekly_sales_subquery.c.sold_qty_week, 0).label("online_sales"),
            )
            .outerjoin(
                weekly_sales_subquery,
                Product.id == weekly_sales_subquery.c.product_id,
            )
            .filter(Product.is_active == True)
            .all()
        )

        # Calcular total y ordenar en Python para sumar el ajuste manual
        ranking: List[ProductSalesRanking] = []
        for p in products_with_weekly_sales:
            online_sales = p.online_sales or 0
            manual_adjustment = p.manual_sales_adjustment or 0
            total_sales = online_sales + manual_adjustment
            
            ranking.append(
                ProductSalesRanking(
                    id=p.id,
                    name=p.name,
                    club_name=p.club_name,
                    sales_count=total_sales,
                    preview_image_url=p.preview_image_url,
                    slug=p.slug,
                )
            )

        # Ordenar: mayor venta primero, luego alfabético como desempate
        ranking.sort(key=lambda x: (-x.sales_count, x.club_name or x.name or ""))
        
        # Limitar resultados
        ranking = ranking[:limit if limit > 0 else 10]

        return SalesRankingResponse(ranking=ranking)

    except Exception as e:
        logger.error(f"Error al obtener ranking de tendencias: {e}", exc_info=True)
        return SalesRankingResponse(ranking=[])


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
        
        # --- Ingresos totales (solo órdenes confirmadas/pagadas) ---
        # Estados válidos: PAID, IN_PRODUCTION, READY_FOR_SHIPMENT, SHIPPED, DELIVERED
        # Excluir: PENDING (no pagado), CANCELLED (cancelado), REFUNDED (reembolsado)
        VALID_REVENUE_STATUSES = ["PAID", "IN_PRODUCTION", "READY_FOR_SHIPMENT", "SHIPPED", "DELIVERED"]
        try:
            # Debug: log all orders with their status and amounts
            all_orders = db.query(Order.id, Order.status, Order.total_amount).all()
            logger.info(f"DEBUG - All orders: {[(o.id, o.status, o.total_amount) for o in all_orders]}")
            
            # Calculate total revenue
            total_revenue = db.query(func.sum(Order.total_amount)).filter(
                Order.status.in_(VALID_REVENUE_STATUSES)
            ).scalar() or 0.0
            
            # Debug: log matching orders
            matching_orders = db.query(Order.id, Order.status, Order.total_amount).filter(
                Order.status.in_(VALID_REVENUE_STATUSES)
            ).all()
            logger.info(f"DEBUG - Matching orders for revenue: {[(o.id, o.status, o.total_amount) for o in matching_orders]}")
            logger.info(f"DEBUG - Total revenue calculated: {total_revenue}")
        except Exception as e:
            logger.warning(f"Error al calcular ingresos: {e}")
            total_revenue = 0.0
        
        # --- Pedidos activos (no cancelados ni reembolsados) ---
        try:
            active_orders = db.query(func.count(Order.id)).filter(
                ~Order.status.in_(["CANCELLED", "REFUNDED", "CART"])
            ).scalar() or 0
        except Exception as e:
            logger.warning(f"Error al contar pedidos activos: {e}")
            active_orders = db.query(func.count(Order.id)).scalar() or 0
        
        # --- Clientes registrados (total) ---
        # Nota: User.created_at no existe en el modelo, así que contamos todos los usuarios
        # El dashboard ahora usa unique_visitors para mostrar visitantes del sitio
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        try:
            new_customers = db.query(func.count(User.id)).scalar() or 0
        except Exception as e:
            logger.warning(f"Error al contar clientes: {e}")
            db.rollback()
            new_customers = 0
        
        # --- Visitantes únicos (últimos 30 días) ---
        try:
            unique_visitors = db.query(func.count(UniqueVisit.id)).filter(
                UniqueVisit.created_at >= thirty_days_ago
            ).scalar() or 0
        except Exception as e:
            logger.warning(f"Error al contar visitantes únicos: {e}")
            db.rollback()
            unique_visitors = 0
        
        # --- Top productos vendidos (basado en OrderItems - excluyendo cancelados/reembolsados/carritos + ajuste manual) ---
        EXCLUDED_STATUSES_SALES = ["CANCELLED", "REFUNDED", "CART"]
        top_products = []
        try:
            # Primero obtener ventas online por producto
            online_sales_query = (
                db.query(
                    OrderItem.product_name,
                    OrderItem.product_id,
                    func.sum(OrderItem.quantity).label("online_quantity"),
                    func.sum(OrderItem.unit_price * OrderItem.quantity).label("total_revenue")
                )
                .join(Order, OrderItem.order_id == Order.id)
                .filter(~Order.status.in_(EXCLUDED_STATUSES_SALES))
                .group_by(OrderItem.product_name, OrderItem.product_id)
                .all()
            )
            
            # Crear diccionario con totales por producto_id
            product_sales_dict = {}
            
            for item in online_sales_query:
                product = None
                manual_adjustment = 0
                if item.product_id:
                    product = db.query(Product).filter(Product.id == item.product_id).first()
                    if product:
                        manual_adjustment = product.manual_sales_adjustment or 0
                
                category_name = None
                stock = 0
                price = 0.0
                slug = None
                
                if product:
                    if product.category:
                        category_name = product.category.name
                    stock = product.stock or 0
                    price = product.price or 0.0
                    slug = product.slug
                
                online_quantity = item.online_quantity or 0
                total_quantity = online_quantity + manual_adjustment
                product_revenue = float(item.total_revenue) if item.total_revenue else 0.0
                
                # Calcular precio promedio de venta real (total_revenue / online_quantity)
                # Esto muestra el precio real pagado, no el precio del catálogo
                avg_sale_price = product_revenue / online_quantity if online_quantity > 0 else (product.price if product else 0.0)
                
                key = item.product_id or item.product_name
                product_sales_dict[key] = {
                    "name": item.product_name,
                    "category": category_name,
                    "total_quantity": total_quantity,
                    "stock": stock,
                    "price": avg_sale_price,  # Precio promedio de venta real
                    "total_revenue": product_revenue,
                    "slug": slug
                }
            
            # Agregar productos con solo ventas manuales (sin órdenes online)
            manual_only_products = db.query(Product).filter(
                Product.manual_sales_adjustment > 0,
                Product.is_active == True
            ).all()
            
            for product in manual_only_products:
                if product.id not in product_sales_dict:
                    category_name = product.category.name if product.category else None
                    product_sales_dict[product.id] = {
                        "name": product.name,
                        "category": category_name,
                        "total_quantity": product.manual_sales_adjustment or 0,
                        "stock": product.stock or 0,
                        "price": product.price or 0.0,
                        "total_revenue": 0.0,  # Sin revenue real si no hay órdenes
                        "slug": product.slug
                    }
            
            # Ordenar por cantidad total y tomar top 4
            product_sales = list(product_sales_dict.values())
            product_sales.sort(key=lambda x: -x["total_quantity"])
            for ps in product_sales[:4]:
                top_products.append(TopProductStats(
                    name=ps["name"],
                    category=ps["category"],
                    total_quantity=ps["total_quantity"],
                    stock=ps["stock"],
                    price=ps["price"],
                    total_revenue=ps["total_revenue"],
                    slug=ps.get("slug")
                ))
        except Exception as e:
            logger.warning(f"Error al obtener top productos: {e}")
        
        # --- Pedidos recientes (últimos 5, excluyendo carritos y cancelados) ---
        recent_orders = []
        try:
            recent_orders_query = (
                db.query(Order)
                .filter(~Order.status.in_(["CART", "CANCELLED", "REFUNDED"]))  # Excluir carritos y cancelados
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
                    Order.status.in_(VALID_REVENUE_STATUSES),
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

        # --- Breakdown de estados de pedido (para donut) ---
        # 6 categorías detalladas
        order_status_counts = {
            "pending": 0,
            "paid": 0,
            "in_production": 0,
            "ready_for_shipment": 0,
            "shipped": 0,
            "cancelled": 0,
        }
        try:
            status_rows = (
                db.query(Order.status, func.count(Order.id))
                .group_by(Order.status)
                .all()
            )
            for status, count in status_rows:
                val = count or 0
                if status == "PENDING":
                    order_status_counts["pending"] += val
                elif status == "PAID":
                    order_status_counts["paid"] += val
                elif status == "IN_PRODUCTION":
                    order_status_counts["in_production"] += val
                elif status == "READY_FOR_SHIPMENT":
                    order_status_counts["ready_for_shipment"] += val
                elif status in ["SHIPPED", "DELIVERED"]:
                    order_status_counts["shipped"] += val
                elif status in ["CANCELLED", "REFUNDED"]:
                    order_status_counts["cancelled"] += val
        except Exception as e:
            logger.warning(f"Error al calcular breakdown de estados: {e}")

        # --- Serie mensual (dos barras: año actual vs año anterior) ---
        monthly_orders: List[dict] = []
        try:
            now = datetime.utcnow()
            current_year = now.year
            previous_year = current_year - 1

            def month_count(year: int, month: int) -> int:
                start = datetime(year, month, 1)
                if month == 12:
                    end = datetime(year + 1, 1, 1)
                else:
                    end = datetime(year, month + 1, 1)
                return (
                    db.query(func.count(Order.id))
                    .filter(
                        Order.created_at >= start,
                        Order.created_at < end,
                        # Usar los mismos estados válidos para consistencia
                        Order.status.in_(VALID_REVENUE_STATUSES),
                    )
                    .scalar()
                    or 0
                )

            for m in range(1, 13):
                monthly_orders.append({
                    "label": datetime(2000, m, 1).strftime("%b"),
                    "current": month_count(current_year, m),
                    "previous": month_count(previous_year, m),
                })
        except Exception as e:
            logger.warning(f"Error al calcular serie mensual: {e}")
            monthly_orders = []
        
        return DashboardStatsResponse(
            products=products_count,
            categories=categories_count,
            promo_banners=promo_banners_count,
            total_revenue=total_revenue,
            active_orders=active_orders,
            new_customers=new_customers,
            unique_visitors=unique_visitors,
            top_products=top_products,
            recent_orders=recent_orders,
            sales_chart=sales_chart,
            order_status=order_status_counts,
            monthly_orders=monthly_orders,
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
            unique_visitors=0,
            top_products=[],
            recent_orders=[],
            sales_chart=[],
            order_status={"pending": 0, "ready_to_ship": 0, "shipped": 0, "cancelled": 0},
            monthly_orders=[],
        )

