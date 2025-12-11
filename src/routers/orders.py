"""
Router para gestionar órdenes de compra
"""
import logging
import secrets
import string
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Dict, Optional
from pydantic import BaseModel

from ..config import get_settings
from ..database import get_db
from ..models.order import Order, OrderItem, PRODUCTION_STATUS_WAITING_FABRIC, PRODUCTION_STATUS_CUTTING, PRODUCTION_STATUS_SEWING, PRODUCTION_STATUS_PRINTING, PRODUCTION_STATUS_FINISHED
from ..models.user import User
from ..models.notification_email import NotificationEmail
from ..schemas.order_schema import OrderCreate, OrderOut, OrderListOut, OrderUpdate, ProductionStatusUpdate
from ..services.email_service import send_sale_notification_email

logger = logging.getLogger(__name__)
router = APIRouter(tags=["orders"])


def generate_order_number() -> str:
    """
    Genera un número de pedido único y no secuencial.
    Formato: GEPE-XXXXXX donde XXXXXX es un código alfanumérico aleatorio.
    Esto evita que los clientes puedan deducir cuántas ventas se han realizado.
    """
    # Generar 6 caracteres alfanuméricos aleatorios
    chars = string.ascii_uppercase + string.digits
    random_code = ''.join(secrets.choice(chars) for _ in range(6))
    return f"GEPE-{random_code}"


def get_or_create_user(db: Session, email: str, full_name: str = None) -> User:
    """
    Busca un usuario por email. Si no existe, lo crea sin contraseña.
    Esto permite a GEPE tener una base de datos de clientes para enviar promociones.
    """
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        logger.info(f"Creando nuevo usuario sin contraseña para email: {email}")
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=None  # Usuario sin contraseña, puede registrarse después
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Usuario creado con ID: {user.id}")
    
    return user


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_input: OrderCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva orden de compra.
    
    - Si el email no existe como usuario, crea uno automáticamente (sin contraseña)
    - Calcula el total basado en los items
    - Guarda los items de la orden
    """
    try:
        # Verificar si ya existe una orden con este external_reference o payment_id
        # Esto evita crear órdenes duplicadas si alguien recarga la página o copia la URL
        if order_input.external_reference:
            existing_order = db.query(Order).filter(
                Order.external_reference == order_input.external_reference
            ).first()
            if existing_order:
                logger.info(f"Orden ya existe con external_reference: {order_input.external_reference}, retornando orden existente (ID: {existing_order.id})")
                return existing_order

        if order_input.payment_id:
            existing_order = db.query(Order).filter(
                Order.payment_id == order_input.payment_id
            ).first()
            if existing_order:
                logger.info(f"Orden ya existe con payment_id: {order_input.payment_id}, retornando orden existente (ID: {existing_order.id})")
                return existing_order
        
        # Obtener o crear usuario
        user = get_or_create_user(
            db, 
            order_input.customer_email, 
            order_input.customer_name
        )
        
        # Calcular total
        total_amount = sum(item.unit_price * item.quantity for item in order_input.items)
        
        # Generar número de pedido único (no secuencial para privacidad)
        order_number = generate_order_number()
        # Asegurar que el order_number sea único (muy poco probable que se repita, pero por seguridad)
        while db.query(Order).filter(Order.order_number == order_number).first():
            order_number = generate_order_number()
        
        # Crear orden
        order = Order(
            user_id=user.id,
            order_number=order_number,
            status="PENDING",
            total_amount=total_amount,
            external_reference=order_input.external_reference,
            payment_id=order_input.payment_id,
            customer_email=order_input.customer_email,
            customer_name=order_input.customer_name,
            customer_phone=order_input.customer_phone,
            customer_dni=order_input.customer_dni,
            shipping_method=order_input.shipping_method,
            shipping_address=order_input.shipping_address,
            shipping_city=order_input.shipping_city
        )
        
        db.add(order)
        db.flush()  # Para obtener el order.id antes de commit
        
        # Crear items de la orden
        for item_input in order_input.items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item_input.product_id,
                product_name=item_input.product_name,
                product_size=item_input.product_size,
                quantity=item_input.quantity,
                unit_price=item_input.unit_price
            )
            db.add(order_item)
        
        db.commit()
        db.refresh(order)
        
        logger.info(f"Orden creada exitosamente: ID={order.id}, Email={order.customer_email}, Total=${total_amount}")
        
        # Enviar notificación por email a los administradores
        try:
            admin_emails = db.query(NotificationEmail).filter(
                NotificationEmail.verified == True
            ).all()
            if admin_emails:
                email_list = [e.email for e in admin_emails]
                await send_sale_notification_email(order, email_list)
                logger.info(f"Notificación de venta enviada a {len(email_list)} administradores")
            else:
                logger.info("No hay emails de administradores verificados para enviar notificación")
        except Exception as e:
            # No bloquear la creación de la orden si falla el envío del email
            logger.warning(f"Error al enviar notificación de venta (no crítico): {str(e)}")
        
        return order
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al crear orden: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear la orden: {str(e)}"
        )


def _list_orders_impl(
    status_filter: str = None,
    search: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = None
):
    """
    Implementación compartida para listar órdenes.
    """
    query = db.query(Order).options(joinedload(Order.items))
    
    if status_filter:
        query = query.filter(Order.status == status_filter)

    if search:
        search_term = f"%{search.lower()}%"
        # Búsqueda flexible: ID, número de orden, email, nombre
        criteria = [
            Order.order_number.ilike(search_term),
            Order.customer_email.ilike(search_term),
            Order.customer_name.ilike(search_term),
            Order.external_reference.ilike(search_term)
        ]
        # Si es numérico, intentar buscar por ID exacto
        if search.isdigit():
            criteria.append(Order.id == int(search))
            
        from sqlalchemy import or_
        query = query.filter(or_(*criteria))
    
    orders = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    
    # Agregar count de items y nombre del primer producto a cada orden
    result = []
    for order in orders:
        # Obtener el nombre del primer producto para vista previa
        first_product_name = None
        if order.items and len(order.items) > 0:
            first_product_name = order.items[0].product_name
            # Si hay más de un producto, agregar indicador
            if len(order.items) > 1:
                first_product_name += f" y {len(order.items) - 1} más"
        
        order_dict = {
            "id": order.id,
            "order_number": order.order_number,
            "customer_email": order.customer_email,
            "customer_name": order.customer_name,
            "status": order.status,
            "total_amount": order.total_amount,
            "created_at": order.created_at,
            "items_count": len(order.items),
            "first_product_name": first_product_name,
            "payment_id": order.payment_id,
            "external_reference": order.external_reference,
            "shipping_method": order.shipping_method,
            "shipping_address": order.shipping_address,
            "shipping_city": order.shipping_city,
            "tracking_code": order.tracking_code,
            "tracking_company": order.tracking_company,
            "tracking_branch_address": order.tracking_branch_address,
            "tracking_attachment_url": order.tracking_attachment_url,
            "production_status": order.production_status
        }
        result.append(OrderListOut(**order_dict))
    
    return result


@router.get("/orders", response_model=List[OrderListOut])
@router.get("/orders/", response_model=List[OrderListOut])
async def list_orders(
    status_filter: str = None,
    search: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lista todas las órdenes. Opcionalmente filtra por status o texto de búsqueda.
    
    - Para admin: ver todas las órdenes
    - Puede filtrar por status: PENDING, PAID, CANCELLED, REFUNDED
    - Puede buscar por: ID, número de orden, email, nombre
    """
    try:
        return _list_orders_impl(status_filter, search, skip, limit, db)
    except Exception as e:
        logger.error(f"Error al listar órdenes: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las órdenes: {str(e)}"
        )


@router.get("/orders/user/{user_email}", response_model=List[OrderListOut])
async def list_user_orders(
    user_email: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Lista todas las órdenes de un usuario específico por email.
    Útil para que el usuario vea su historial de compras.
    No requiere autenticación - permite a usuarios no registrados ver sus pedidos.
    """
    try:
        orders = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.customer_email == user_email)
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        result = []
        for order in orders:
            # Obtener el nombre del primer producto para vista previa
            first_product_name = None
            if order.items and len(order.items) > 0:
                first_product_name = order.items[0].product_name
                # Si hay más de un producto, agregar indicador
                if len(order.items) > 1:
                    first_product_name += f" y {len(order.items) - 1} más"
            
            order_dict = {
                "id": order.id,
                "order_number": order.order_number,  # Incluir order_number
                "customer_email": order.customer_email,
                "customer_name": order.customer_name,
                "status": order.status,
                "total_amount": order.total_amount,
                "created_at": order.created_at,
                "items_count": len(order.items),
                "first_product_name": first_product_name,
                "payment_id": order.payment_id,
                "external_reference": order.external_reference,
                "shipping_method": order.shipping_method,
                "shipping_address": order.shipping_address,
                "shipping_city": order.shipping_city,
                "tracking_code": order.tracking_code,
            "tracking_company": order.tracking_company,
            "tracking_branch_address": order.tracking_branch_address,
            "tracking_attachment_url": order.tracking_attachment_url,
                "production_status": order.production_status
            }
            result.append(OrderListOut(**order_dict))
        
        logger.info(f"Obtenidas {len(result)} órdenes para el usuario {user_email}")
        return result
    except Exception as e:
        logger.error(f"Error al obtener órdenes del usuario {user_email}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener las órdenes del usuario: {str(e)}"
        )


@router.get("/orders/by-number/{order_number}", response_model=OrderOut)
async def get_order_by_number(
    order_number: str,
    email: str = None,  # Query parameter para validar que el usuario tiene acceso (opcional para admins)
    db: Session = Depends(get_db)
):
    """
    Obtiene los detalles completos de una orden específica por order_number.
    
    SEGURIDAD: 
    - Si se proporciona email: valida que el email coincida con el del pedido (para usuarios normales)
    - Si NO se proporciona email: permite el acceso (asumiendo que es un admin desde el dashboard)
    Esto previene que usuarios normales vean pedidos de otros usuarios, pero permite a admins ver todos los pedidos.
    """
    order = db.query(Order).filter(Order.order_number == order_number).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden {order_number} no encontrada"
        )
    
    # Si se proporciona email, validar que coincida (para usuarios normales)
    if email:
        if email.lower().strip() != order.customer_email.lower().strip():
            logger.warning(f"Intento de acceso no autorizado: email {email} intentó ver orden {order_number} (pertenece a {order.customer_email})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para ver este pedido. Solo puedes ver tus propios pedidos."
            )
        logger.info(f"Acceso autorizado a orden {order_number} para email {email}")
    else:
        # Si no se proporciona email, asumir que es un admin (desde el dashboard)
        logger.info(f"Acceso a orden {order_number} sin email (modo admin)")
    
    return order


# =====================================================
# MODELOS Y FUNCIONES PARA PRODUCCIÓN (TALLER)
# =====================================================

# Lista de estados de producción válidos
VALID_PRODUCTION_STATUSES = [
    PRODUCTION_STATUS_WAITING_FABRIC,
    PRODUCTION_STATUS_CUTTING,
    PRODUCTION_STATUS_SEWING,
    PRODUCTION_STATUS_PRINTING,
    PRODUCTION_STATUS_FINISHED
]


class ProductionOrderItem(BaseModel):
    """Item de orden para producción (sin precio)"""
    id: int
    product_name: str
    product_size: Optional[str]
    quantity: int


class ProductionOrder(BaseModel):
    """Orden para producción (sin precio)"""
    id: int
    order_number: Optional[str]
    customer_name: Optional[str]
    production_status: Optional[str]
    created_at: str
    items: List[ProductionOrderItem]
    items_count: int


class ProductionOrdersResponse(BaseModel):
    """Respuesta con órdenes agrupadas por estado de producción"""
    waiting_fabric: List[ProductionOrder]
    cutting: List[ProductionOrder]
    sewing: List[ProductionOrder]
    printing: List[ProductionOrder]
    finished: List[ProductionOrder]
    ready_for_shipment: List[ProductionOrder]
    total_count: int


def _order_to_production_order(order: Order) -> ProductionOrder:
    """Convierte una orden a ProductionOrder (sin precios)"""
    items = [
        ProductionOrderItem(
            id=item.id,
            product_name=item.product_name,
            product_size=item.product_size,
            quantity=item.quantity
        )
        for item in order.items
    ]
    
    return ProductionOrder(
        id=order.id,
        order_number=order.order_number,
        customer_name=order.customer_name,
        production_status=order.production_status,
        created_at=order.created_at.isoformat() if order.created_at else "",
        items=items,
        items_count=len(items)
    )


# =====================================================
# GET /orders/production - Debe estar ANTES de /orders/{order_id}
# para evitar que FastAPI interprete "production" como order_id
# =====================================================

@router.get("/orders/production", response_model=ProductionOrdersResponse)
async def list_production_orders(
    db: Session = Depends(get_db)
):
    """
    Lista todos los pedidos PAGADOS o READY_FOR_SHIPMENT para producción, agrupados por estado de producción.
    
    IMPORTANTE: Solo muestra pedidos con status='PAID'.
    Los precios NO se incluyen en la respuesta (el taller no necesita verlos).
    
    Los pedidos se agrupan en las siguientes columnas:
    - waiting_fabric: En espera de tela
    - cutting: Corte
    - sewing: Confección
    - printing: Estampado
    - finished: Terminado
    """
    try:
        # Obtener pedidos en producción (pagados o listos para enviar)
        orders = (
            db.query(Order)
            .options(joinedload(Order.items))
            .filter(Order.status.in_(["PAID", "READY_FOR_SHIPMENT"]))
            .order_by(Order.created_at.asc())  # Los más antiguos primero
            .all()
        )
        
        # Agrupar por estado de producción
        waiting_fabric = []
        cutting = []
        sewing = []
        printing = []
        finished = []
        ready_for_shipment = []
        
        for order in orders:
            prod_order = _order_to_production_order(order)
            
            if order.status == "READY_FOR_SHIPMENT":
                ready_for_shipment.append(prod_order)
            elif order.production_status == PRODUCTION_STATUS_CUTTING:
                cutting.append(prod_order)
            elif order.production_status == PRODUCTION_STATUS_SEWING:
                sewing.append(prod_order)
            elif order.production_status == PRODUCTION_STATUS_PRINTING:
                printing.append(prod_order)
            elif order.production_status == PRODUCTION_STATUS_FINISHED:
                finished.append(prod_order)
            else:
                # Por defecto, incluyendo WAITING_FABRIC o None
                waiting_fabric.append(prod_order)
        
        return ProductionOrdersResponse(
            waiting_fabric=waiting_fabric,
            cutting=cutting,
            sewing=sewing,
            printing=printing,
            finished=finished,
            ready_for_shipment=ready_for_shipment,
            total_count=len(orders)
        )
        
    except Exception as e:
        logger.error(f"Error al obtener pedidos de producción: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener pedidos de producción: {str(e)}"
        )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    email: str = None,  # Query parameter para validar que el usuario tiene acceso (opcional para admins)
    db: Session = Depends(get_db)
):
    """
    Obtiene los detalles completos de una orden específica por ID interno.
    DEPRECATED: Usar /orders/by-number/{order_number} en su lugar.
    
    SEGURIDAD: 
    - Si se proporciona email: valida que el email coincida con el del pedido (para usuarios normales)
    - Si NO se proporciona email: permite el acceso (asumiendo que es un admin desde el dashboard)
    Esto previene que usuarios normales vean pedidos de otros usuarios, pero permite a admins ver todos los pedidos.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden {order_id} no encontrada"
        )
    
    # Si se proporciona email, validar que coincida (para usuarios normales)
    if email:
        if email.lower().strip() != order.customer_email.lower().strip():
            logger.warning(f"Intento de acceso no autorizado: email {email} intentó ver orden {order_id} (pertenece a {order.customer_email})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para ver este pedido. Solo puedes ver tus propios pedidos."
            )
        logger.info(f"Acceso autorizado a orden {order_id} para email {email}")
    else:
        # Si no se proporciona email, asumir que es un admin (desde el dashboard)
        logger.info(f"Acceso a orden {order_id} sin email (modo admin)")
    
    return order


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order(
    order_id: int,
    order_update: OrderUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza el status de una orden.
    
    - Útil para que admin cambie el estado de las órdenes
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden {order_id} no encontrada"
        )
    
    # Actualizar campos si están presentes
    if order_update.status:
        order.status = order_update.status
        logger.info(f"Orden {order_id} actualizada a status: {order_update.status}")
    
    if order_update.payment_id:
        order.payment_id = order_update.payment_id
    
    if order_update.shipping_address is not None:
        order.shipping_address = order_update.shipping_address
        logger.info(f"Orden {order_id}: dirección de envío actualizada")
    
    if order_update.shipping_city is not None:
        order.shipping_city = order_update.shipping_city
        logger.info(f"Orden {order_id}: ciudad de envío actualizada")
    
    if order_update.tracking_code is not None:
        order.tracking_code = order_update.tracking_code
        logger.info(f"Orden {order_id}: código de seguimiento actualizado: {order_update.tracking_code}")

    if order_update.tracking_company is not None:
        order.tracking_company = order_update.tracking_company
        logger.info(f"Orden {order_id}: empresa de envío actualizada: {order_update.tracking_company}")

    if order_update.tracking_branch_address is not None:
        order.tracking_branch_address = order_update.tracking_branch_address
        logger.info(f"Orden {order_id}: sucursal de envío actualizada: {order_update.tracking_branch_address}")

    if order_update.tracking_attachment_url is not None:
        order.tracking_attachment_url = order_update.tracking_attachment_url
        logger.info(f"Orden {order_id}: adjunto de seguimiento actualizado")
    
    if order_update.production_status is not None:
        order.production_status = order_update.production_status
        logger.info(f"Orden {order_id}: estado de producción actualizado: {order_update.production_status}")
    
    try:
        db.commit()
        db.refresh(order)
        return order
    except Exception as e:
        db.rollback()
        logger.error(f"Error al actualizar orden {order_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar la orden: {str(e)}"
        )


class ProductStats(BaseModel):
    product_name: str
    total_quantity: int
    total_orders: int
    sizes: Dict[str, int]


class SizeStats(BaseModel):
    size: str
    total_quantity: int
    products: List[str]


class ProductionStats(BaseModel):
    products: List[ProductStats]
    sizes: List[SizeStats]
    total_pending_orders: int
    total_paid_orders: int
    total_pending_amount: float


class PaymentStats(BaseModel):
    total_revenue: float
    total_paid: int
    total_pending: int
    total_cancelled: int
    total_refunded: int
    average_payment: float
    revenue_today: float
    revenue_this_week: float
    revenue_this_month: float


@router.get("/orders/stats/production", response_model=ProductionStats)
async def get_production_stats(
    db: Session = Depends(get_db)
):
    """
    Obtiene estadísticas de producción para el dashboard de producción.
    Incluye productos más vendidos, talles más pedidos, y resumen de pedidos pendientes.
    """
    try:
        # Obtener pedidos pendientes o pagados (que necesitan fabricación)
        pending_orders = db.query(Order).filter(
            Order.status.in_(["PENDING", "PAID"])
        ).all()
        
        total_pending_orders = len([o for o in pending_orders if o.status == "PENDING"])
        total_paid_orders = len([o for o in pending_orders if o.status == "PAID"])
        total_pending_amount = sum(o.total_amount for o in pending_orders)
        
        # Obtener todos los items de pedidos pendientes o pagados
        order_ids = [o.id for o in pending_orders]
        
        if not order_ids:
            return ProductionStats(
                products=[],
                sizes=[],
                total_pending_orders=0,
                total_paid_orders=0,
                total_pending_amount=0.0
            )
        
        items = db.query(OrderItem).filter(
            OrderItem.order_id.in_(order_ids)
        ).all()
        
        # Agrupar por producto
        product_map: Dict[str, Dict] = {}
        size_map: Dict[str, Dict] = {}
        
        for item in items:
            # Estadísticas por producto
            if item.product_name not in product_map:
                product_map[item.product_name] = {
                    "total_quantity": 0,
                    "total_orders": set(),
                    "sizes": {}
                }
            
            product_map[item.product_name]["total_quantity"] += item.quantity
            product_map[item.product_name]["total_orders"].add(item.order_id)
            
            if item.product_size:
                if item.product_size not in product_map[item.product_name]["sizes"]:
                    product_map[item.product_name]["sizes"][item.product_size] = 0
                product_map[item.product_name]["sizes"][item.product_size] += item.quantity
            
            # Estadísticas por talle
            if item.product_size:
                if item.product_size not in size_map:
                    size_map[item.product_size] = {
                        "total_quantity": 0,
                        "products": set()
                    }
                
                size_map[item.product_size]["total_quantity"] += item.quantity
                size_map[item.product_size]["products"].add(item.product_name)
        
        # Convertir a modelos de respuesta
        product_stats = [
            ProductStats(
                product_name=name,
                total_quantity=data["total_quantity"],
                total_orders=len(data["total_orders"]),
                sizes=data["sizes"]
            )
            for name, data in product_map.items()
        ]
        product_stats.sort(key=lambda x: x.total_quantity, reverse=True)
        
        size_stats = [
            SizeStats(
                size=size,
                total_quantity=data["total_quantity"],
                products=list(data["products"])
            )
            for size, data in size_map.items()
        ]
        size_stats.sort(key=lambda x: x.total_quantity, reverse=True)
        
        return ProductionStats(
            products=product_stats,
            sizes=size_stats,
            total_pending_orders=total_pending_orders,
            total_paid_orders=total_paid_orders,
            total_pending_amount=total_pending_amount
        )
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de producción: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas: {str(e)}"
        )


@router.get("/orders/stats/payments", response_model=PaymentStats)
async def get_payment_stats(
    db: Session = Depends(get_db)
):
    """
    Obtiene estadísticas de pagos para el dashboard de pagos.
    """
    try:
        from datetime import datetime, timedelta
        
        # Obtener todas las órdenes
        all_orders = db.query(Order).all()
        
        # Calcular estadísticas
        paid_orders = [o for o in all_orders if o.status == "PAID"]
        pending_orders = [o for o in all_orders if o.status == "PENDING"]
        cancelled_orders = [o for o in all_orders if o.status == "CANCELLED"]
        refunded_orders = [o for o in all_orders if o.status == "REFUNDED"]
        
        total_revenue = sum(o.total_amount for o in paid_orders)
        total_paid = len(paid_orders)
        total_pending = len(pending_orders)
        total_cancelled = len(cancelled_orders)
        total_refunded = len(refunded_orders)
        average_payment = total_revenue / total_paid if total_paid > 0 else 0.0
        
        # Estadísticas por período
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        revenue_today = sum(
            o.total_amount for o in paid_orders
            if o.created_at >= today_start
        )
        
        revenue_this_week = sum(
            o.total_amount for o in paid_orders
            if o.created_at >= week_start
        )
        
        revenue_this_month = sum(
            o.total_amount for o in paid_orders
            if o.created_at >= month_start
        )
        
        return PaymentStats(
            total_revenue=total_revenue,
            total_paid=total_paid,
            total_pending=total_pending,
            total_cancelled=total_cancelled,
            total_refunded=total_refunded,
            average_payment=average_payment,
            revenue_today=revenue_today,
            revenue_this_week=revenue_this_week,
            revenue_this_month=revenue_this_month
        )
        
    except Exception as e:
        logger.error(f"Error al obtener estadísticas de pagos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estadísticas de pagos: {str(e)}"
        )




# =====================================================
# ENDPOINTS DE PRODUCCIÓN (TALLER) - PATCH y POST
# =====================================================




@router.patch("/orders/{order_id}/production-status", response_model=OrderOut)
async def update_production_status(
    order_id: int,
    status_update: ProductionStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza el estado de producción de una orden.
    
    Estados válidos:
    - WAITING_FABRIC: En espera de tela
    - CUTTING: Corte
    - SEWING: Confección
    - PRINTING: Estampado
    - FINISHED: Terminado
    
    Nota: Solo se puede actualizar órdenes con status='PAID'.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden {order_id} no encontrada"
        )
    
    # Verificar que la orden esté pagada
    if order.status != "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede actualizar el estado de producción de órdenes pagadas. Estado actual: {order.status}"
        )
    
    # Validar el estado de producción
    if status_update.production_status not in VALID_PRODUCTION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado de producción inválido. Estados válidos: {', '.join(VALID_PRODUCTION_STATUSES)}"
        )
    
    try:
        old_status = order.production_status
        order.production_status = status_update.production_status
        db.commit()
        db.refresh(order)
        
        logger.info(f"Orden {order_id} ({order.order_number}): estado de producción actualizado de {old_status} a {status_update.production_status}")
        
        return order
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al actualizar estado de producción: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar estado de producción: {str(e)}"
        )


class FinishProductionResponse(BaseModel):
    """Respuesta al terminar producción"""
    success: bool
    message: str
    order_number: Optional[str]
    email_sent: bool


@router.post("/orders/{order_id}/finish-production", response_model=FinishProductionResponse)
async def finish_production(
    order_id: int,
    db: Session = Depends(get_db)
):
    """
    Marca una orden como terminada en producción y lista para enviar.
    
    Acciones que realiza:
    1. Cambia production_status a 'FINISHED'
    2. Cambia status de la orden a 'READY_FOR_SHIPMENT'
    3. Envía email al cliente notificando que su pedido está listo
    
    Nota: Solo se puede terminar órdenes con status='PAID' y production_status='FINISHED'.
    """
    order = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.id == order_id)
        .first()
    )
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orden {order_id} no encontrada"
        )
    
    # Verificar que la orden esté pagada
    if order.status != "PAID":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Solo se puede terminar producción de órdenes pagadas. Estado actual: {order.status}"
        )
    
    try:
        # Marcar como terminado
        order.production_status = PRODUCTION_STATUS_FINISHED
        order.status = "READY_FOR_SHIPMENT"
        db.commit()
        
        logger.info(f"Orden {order_id} ({order.order_number}): producción terminada, lista para enviar")
        
        # Intentar enviar email al cliente
        email_sent = False
        try:
            from ..services.email_service import send_production_complete_email
            email_sent = await send_production_complete_email(order)
            if email_sent:
                logger.info(f"Email de producción completa enviado a {order.customer_email}")
            else:
                logger.warning(f"No se pudo enviar email a {order.customer_email}")
        except ImportError:
            logger.warning("Servicio de email no configurado, no se enviará notificación al cliente")
        except Exception as email_error:
            logger.error(f"Error al enviar email: {str(email_error)}")
        
        return FinishProductionResponse(
            success=True,
            message=f"Producción terminada. El pedido {order.order_number} está listo para enviar.",
            order_number=order.order_number,
            email_sent=email_sent
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al terminar producción: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al terminar producción: {str(e)}"
        )

