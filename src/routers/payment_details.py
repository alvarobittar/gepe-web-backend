"""
Router para gestionar información financiera detallada de pagos (para Contador)
"""
import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from datetime import datetime as dt

from ..database import get_db
from ..models.payment import Payment
from ..models.order import Order
from ..schemas.payment_detail_schema import PaymentOut, PaymentListOut
from ..routers.payments import get_mp_sdk

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payment-details"])


def get_payment_method_label(payment: Payment) -> str:
    """Genera una etiqueta legible del método de pago"""
    
    # Mapeo de payment_method_id (marca de tarjeta o método específico)
    method_labels = {
        "visa": "Visa",
        "master": "Mastercard",
        "amex": "American Express",
        "naranja": "Naranja",
        "cabal": "Cabal",
        "argencard": "Argencard",
        "diners": "Diners Club",
        "rapipago": "Rapipago",
        "pagofacil": "Pago Fácil",
        "account_money": "Dinero en cuenta MP",
        "bank_transfer": "Transferencia bancaria",
    }
    
    # Mapeo de payment_type_id (tipo de pago)
    type_labels = {
        "credit_card": "Tarjeta de crédito",
        "debit_card": "Tarjeta de débito",
        "ticket": "Ticket",
        "account_money": "Dinero en cuenta MP",
        "bank_transfer": "Transferencia bancaria",
        "atm": "Cajero automático",
    }
    
    # Si tenemos payment_method_id, usarlo (es más específico)
    if payment.payment_method_id:
        method_name = method_labels.get(payment.payment_method_id.lower(), payment.payment_method_id.upper())
        
        # Si es una tarjeta y tenemos los últimos 4 dígitos, agregarlos
        if payment.card_last_four_digits and payment.payment_type_id in ["credit_card", "debit_card"]:
            return f"{method_name} terminada en {payment.card_last_four_digits}"
        
        return method_name
    
    # Si no hay payment_method_id, usar payment_type_id
    if payment.payment_type_id:
        type_name = type_labels.get(payment.payment_type_id.lower(), payment.payment_type_id.replace("_", " ").title())
        
        # Si es ticket y tenemos payment_method_id en otro lugar, intentar obtenerlo
        if payment.payment_type_id == "ticket":
            # Para tickets, el método puede estar en otro campo
            return type_name
        
        return type_name
    
    # Si no hay ninguna información, retornar desconocido
    return "Desconocido"


@router.post("/payments/sync")
async def sync_payments_from_orders(
    db: Session = Depends(get_db)
):
    """
    Sincroniza pagos desde órdenes existentes que tienen payment_id.
    Útil para migrar datos existentes o cuando falta un webhook.
    """
    try:
        # Buscar órdenes con payment_id que no tienen registro en payments
        orders_with_payment = db.query(Order).filter(
            Order.payment_id.isnot(None),
            Order.payment_id != ""
        ).all()
        
        sdk = get_mp_sdk()
        synced_count = 0
        errors = []
        
        for order in orders_with_payment:
            # Verificar si ya existe el pago
            existing_payment = db.query(Payment).filter(
                Payment.mp_payment_id == order.payment_id
            ).first()
            
            if existing_payment:
                continue  # Ya existe, saltar
            
            try:
                # Obtener información del pago desde Mercado Pago
                payment_response = sdk.payment().get(order.payment_id)
                
                if payment_response["status"] != 200:
                    errors.append(f"Error al obtener pago {order.payment_id}: {payment_response.get('response', {})}")
                    continue
                
                payment = payment_response["response"]
                
                # Extraer información del método de pago
                # La información puede estar en diferentes lugares según el tipo de pago
                card_info = payment.get("card", {})
                
                # payment_method_id puede estar en payment.payment_method_id o payment.card.payment_method_id
                payment_method_id = payment.get("payment_method_id") or card_info.get("payment_method_id")
                
                # payment_type_id indica el tipo: credit_card, debit_card, ticket, account_money, etc.
                payment_type_id = payment.get("payment_type_id")
                
                # Para tarjetas, los últimos 4 dígitos están en card.last_four_digits
                card_last_four = card_info.get("last_four_digits") if card_info else None
                
                # Nombre del titular de la tarjeta
                card_holder = card_info.get("cardholder", {}).get("name") if card_info else None
                
                # Logging para debug
                logger.info(
                    f"Sincronizando pago {order.payment_id} - "
                    f"payment_method_id: {payment_method_id}, "
                    f"payment_type_id: {payment_type_id}, "
                    f"card_last_four: {card_last_four}"
                )
                
                # Extraer información de reembolsos
                refunds = payment.get("refunds", [])
                refunded_amount = sum(float(refund.get("amount", 0)) for refund in refunds)
                refunded_count = len(refunds)
                
                # Verificar contracargos
                has_chargeback = "true" if payment.get("chargeback") or payment.get("chargebacks") else "false"
                
                # Extraer fechas
                date_created_str = payment.get("date_created")
                date_approved_str = payment.get("date_approved")
                date_last_updated_str = payment.get("date_last_updated")
                
                date_created = dt.fromisoformat(date_created_str.replace("Z", "+00:00")) if date_created_str else None
                date_approved = dt.fromisoformat(date_approved_str.replace("Z", "+00:00")) if date_approved_str else None
                date_last_updated = dt.fromisoformat(date_last_updated_str.replace("Z", "+00:00")) if date_last_updated_str else None
                
                # Crear registro de Payment
                db_payment = Payment(
                    order_id=order.id,
                    mp_payment_id=order.payment_id,
                    transaction_amount=float(payment.get("transaction_amount", 0)),
                    currency_id=payment.get("currency_id", "ARS"),
                    payment_method_id=payment_method_id,
                    payment_type_id=payment_type_id,
                    card_last_four_digits=card_last_four,
                    card_holder_name=card_holder,
                    status=payment.get("status", "pending"),
                    status_detail=payment.get("status_detail"),
                    refunded_amount=refunded_amount,
                    refunded_count=refunded_count,
                    has_chargeback=has_chargeback,
                    date_created=date_created or dt.utcnow(),
                    date_approved=date_approved,
                    date_last_updated=date_last_updated,
                    mp_raw_data=json.dumps(payment)
                )
                db.add(db_payment)
                synced_count += 1
                
            except Exception as e:
                logger.error(f"Error al sincronizar pago {order.payment_id}: {str(e)}", exc_info=True)
                errors.append(f"Error al sincronizar pago {order.payment_id}: {str(e)}")
        
        db.commit()
        
        return {
            "synced": synced_count,
            "errors": errors,
            "message": f"Se sincronizaron {synced_count} pagos"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al sincronizar pagos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar pagos: {str(e)}"
        )


@router.post("/orders/sync-payment-status")
async def sync_orders_payment_status(
    db: Session = Depends(get_db)
):
    """
    Sincroniza el estado de órdenes basándose en los pagos de MercadoPago.
    
    Útil para corregir órdenes que quedaron en PENDING pero tienen pagos aprobados
    (por ejemplo, debido a race conditions entre webhook y creación de orden).
    """
    try:
        from ..models.order import Order, PRODUCTION_STATUS_WAITING_FABRIC
        from ..services.email_service import send_order_confirmation_email
        
        # Buscar órdenes en PENDING
        pending_orders = db.query(Order).filter(Order.status == "PENDING").all()
        
        synced_count = 0
        results = []
        
        for order in pending_orders:
            # Buscar payment aprobado para esta orden
            approved_payment = None
            
            # Primero buscar por payment_id si existe
            if order.payment_id:
                approved_payment = db.query(Payment).filter(
                    Payment.mp_payment_id == order.payment_id,
                    Payment.status == "approved"
                ).first()
            
            # Si no, buscar por external_reference en mp_raw_data
            if not approved_payment and order.external_reference:
                payments = db.query(Payment).filter(Payment.status == "approved").all()
                for p in payments:
                    if p.mp_raw_data:
                        try:
                            raw_data = json.loads(p.mp_raw_data)
                            if raw_data.get("external_reference") == order.external_reference:
                                approved_payment = p
                                break
                        except:
                            pass
            
            if approved_payment:
                # ¡Actualizar la orden a PAID!
                order.status = "PAID"
                order.payment_id = approved_payment.mp_payment_id
                order.production_status = PRODUCTION_STATUS_WAITING_FABRIC
                
                # Vincular payment a order si no estaba
                if not approved_payment.order_id:
                    approved_payment.order_id = order.id
                
                synced_count += 1
                results.append({
                    "order_number": order.order_number,
                    "customer_email": order.customer_email,
                    "mp_payment_id": approved_payment.mp_payment_id,
                    "updated_to": "PAID"
                })
                
                logger.info(f"✅ Orden {order.order_number} sincronizada a PAID")
                
                # Enviar email de confirmación si no se ha enviado
                if not order.confirmation_email_sent:
                    try:
                        from sqlalchemy.orm import joinedload
                        order_with_items = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
                        if order_with_items:
                            email_sent = await send_order_confirmation_email(order_with_items)
                            if email_sent:
                                order.confirmation_email_sent = True
                                logger.info(f"✅ Email de confirmación enviado a {order.customer_email}")
                    except Exception as email_error:
                        logger.warning(f"No se pudo enviar email: {str(email_error)}")
        
        db.commit()
        
        return {
            "synced": synced_count,
            "orders": results,
            "message": f"Se sincronizaron {synced_count} órdenes a PAID"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al sincronizar estados de órdenes: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar estados: {str(e)}"
        )



@router.post("/payments/{payment_id}/refund")
async def refund_payment(
    payment_id: int,
    amount: Optional[float] = Query(None, description="Monto a reembolsar. Si no se especifica, se reembolsa el total"),
    db: Session = Depends(get_db)
):
    """
    Realiza un reembolso parcial o total de un pago usando la API de Mercado Pago.
    """
    try:
        # Obtener el pago de la BD
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pago {payment_id} no encontrado"
            )
        
        # Verificar que el pago esté aprobado
        if payment.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede reembolsar un pago con estado '{payment.status}'. Solo se pueden reembolsar pagos aprobados."
            )
        
        # Calcular monto disponible para reembolsar
        available_amount = payment.transaction_amount - payment.refunded_amount
        
        if available_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El pago ya ha sido reembolsado completamente"
            )
        
        # Determinar monto a reembolsar
        refund_amount = amount if amount is not None else available_amount
        
        if refund_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El monto a reembolsar debe ser mayor a 0"
            )
        
        if refund_amount > available_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El monto a reembolsar (${refund_amount}) excede el disponible (${available_amount})"
            )
        
        # Realizar reembolso en Mercado Pago
        sdk = get_mp_sdk()
        
        # Para reembolso parcial, enviar amount en el body
        # Para reembolso total, no enviar amount (o enviar el monto total)
        refund_data = {
            "amount": refund_amount
        } if refund_amount < available_amount else None
        
        # El SDK de Mercado Pago usa refund().create(payment_id, data)
        if refund_data:
            refund_response = sdk.refund().create(payment.mp_payment_id, refund_data)
        else:
            # Reembolso total: no enviar amount
            refund_response = sdk.refund().create(payment.mp_payment_id)
        
        if refund_response["status"] not in [200, 201]:
            error_detail = refund_response.get("response", {})
            logger.error(f"Error al reembolsar pago {payment.mp_payment_id}: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al procesar el reembolso en Mercado Pago: {error_detail}"
            )
        
        refund_result = refund_response["response"]
        
        # Actualizar información del pago en la BD
        # Obtener información actualizada del pago desde MP
        payment_response = sdk.payment().get(payment.mp_payment_id)
        
        if payment_response["status"] == 200:
            updated_payment = payment_response["response"]
            refunds = updated_payment.get("refunds", [])
            refunded_amount = sum(float(refund.get("amount", 0)) for refund in refunds)
            refunded_count = len(refunds)
            
            payment.refunded_amount = refunded_amount
            payment.refunded_count = refunded_count
            
            # Si se reembolsó todo, actualizar estado
            if refunded_amount >= payment.transaction_amount:
                payment.status = "refunded"
            
            db.commit()
        
        logger.info(f"Reembolso exitoso: ${refund_amount} del pago {payment.mp_payment_id}")
        
        return {
            "success": True,
            "refund_id": refund_result.get("id"),
            "refund_amount": refund_amount,
            "refunded_total": payment.refunded_amount,
            "message": f"Reembolso de ${refund_amount} procesado correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al procesar reembolso: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar el reembolso: {str(e)}"
        )


def _list_payments_impl(
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = None
):
    """
    Implementación compartida para listar pagos.
    """
    query = db.query(Payment).options(joinedload(Payment.order))
    
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    
    payments = query.order_by(desc(Payment.date_created)).offset(skip).limit(limit).all()
    
    result = []
    for payment in payments:
        # Obtener información del pedido relacionado si existe
        order_number = None
        customer_email = None
        customer_name = None
        
        if payment.order:
            order_number = payment.order.order_number
            customer_email = payment.order.customer_email
            customer_name = payment.order.customer_name
        
        payment_dict = {
            "id": payment.id,
            "mp_payment_id": payment.mp_payment_id,
            "transaction_amount": payment.transaction_amount,
            "currency_id": payment.currency_id,
            "payment_method_label": get_payment_method_label(payment),
            "status": payment.status,
            "date_created": payment.date_created,
            "date_approved": payment.date_approved,
            "refunded_amount": payment.refunded_amount,
            "has_chargeback": payment.has_chargeback,
            "order_number": order_number,
            "customer_email": customer_email,
            "customer_name": customer_name,
        }
        result.append(PaymentListOut(**payment_dict))
    
    return result


@router.get("/payments", response_model=List[PaymentListOut])
@router.get("/payments/", response_model=List[PaymentListOut])
async def list_payments(
    status_filter: Optional[str] = Query(None, description="Filtrar por estado: approved, pending, rejected, cancelled, refunded"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Lista todos los pagos con información financiera.
    Enfocado en auditoría financiera (no muestra detalles de productos).
    """
    try:
        return _list_payments_impl(status_filter, skip, limit, db)
    except Exception as e:
        logger.error(f"Error al obtener pagos: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los pagos: {str(e)}"
        )


@router.get("/payments/{payment_id}", response_model=PaymentOut)
async def get_payment_detail(
    payment_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene información detallada de un pago específico.
    """
    try:
        payment = db.query(Payment).options(joinedload(Payment.order)).filter(Payment.id == payment_id).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pago {payment_id} no encontrado"
            )
        
        # Obtener información del pedido relacionado
        order_number = None
        customer_email = None
        customer_name = None
        
        if payment.order:
            order_number = payment.order.order_number
            customer_email = payment.order.customer_email
            customer_name = payment.order.customer_name
        
        payment_dict = {
            "id": payment.id,
            "order_id": payment.order_id,
            "mp_payment_id": payment.mp_payment_id,
            "transaction_amount": payment.transaction_amount,
            "currency_id": payment.currency_id,
            "payment_method_id": payment.payment_method_id,
            "payment_type_id": payment.payment_type_id,
            "payment_method_label": get_payment_method_label(payment),  # Calcular etiqueta legible
            "card_last_four_digits": payment.card_last_four_digits,
            "card_holder_name": payment.card_holder_name,
            "status": payment.status,
            "status_detail": payment.status_detail,
            "refunded_amount": payment.refunded_amount,
            "refunded_count": payment.refunded_count,
            "has_chargeback": payment.has_chargeback,
            "date_created": payment.date_created,
            "date_approved": payment.date_approved,
            "date_last_updated": payment.date_last_updated,
            "created_at": payment.created_at,
            "updated_at": payment.updated_at,
            "order_number": order_number,
            "customer_email": customer_email,
            "customer_name": customer_name,
        }
        
        return PaymentOut(**payment_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener detalle del pago: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener el detalle del pago: {str(e)}"
        )


@router.post("/payments/{mp_payment_id}/recover-order")
async def recover_order_from_payment(
    mp_payment_id: str,
    db: Session = Depends(get_db)
):
    """
    Recupera una orden huérfana desde un pago de MercadoPago.
    
    Útil cuando un cliente pagó pero no volvió a la página de éxito,
    por lo que el pago existe pero la orden nunca se creó.
    
    Este endpoint:
    1. Busca el Payment por mp_payment_id
    2. Verifica que no tenga orden asociada
    3. Extrae datos del cliente y productos del mp_raw_data
    4. Crea la Order y OrderItems
    5. Vincula el Payment a la Order
    6. Envía el email de confirmación al cliente
    """
    try:
        import secrets
        import string
        from ..models.order import Order, OrderItem, PRODUCTION_STATUS_WAITING_FABRIC
        from ..models.user import User
        from ..services.email_service import send_order_confirmation_email
        
        # Buscar el pago
        payment = db.query(Payment).filter(Payment.mp_payment_id == mp_payment_id).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pago con ID {mp_payment_id} no encontrado"
            )
        
        # Verificar que no tenga orden asociada
        if payment.order_id:
            existing_order = db.query(Order).filter(Order.id == payment.order_id).first()
            if existing_order:
                return {
                    "success": False,
                    "message": f"Este pago ya tiene una orden asociada: {existing_order.order_number}",
                    "order_number": existing_order.order_number,
                    "order_id": existing_order.id
                }
        
        # Verificar que el pago esté aprobado
        if payment.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se pueden recuperar órdenes de pagos aprobados. Estado actual: {payment.status}"
            )
        
        # Parsear mp_raw_data
        if not payment.mp_raw_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El pago no tiene datos raw de MercadoPago para recuperar"
            )
        
        raw_data = json.loads(payment.mp_raw_data)
        
        # Extraer información del cliente
        payer = raw_data.get("payer", {})
        additional_info = raw_data.get("additional_info", {})
        additional_payer = additional_info.get("payer", {})
        
        customer_email = payer.get("email")
        customer_name = f"{additional_payer.get('first_name', '')} {additional_payer.get('last_name', '')}".strip()
        
        # Si no hay nombre en additional_info, intentar desde card.cardholder
        if not customer_name:
            card = raw_data.get("card", {})
            cardholder = card.get("cardholder", {})
            customer_name = cardholder.get("name", "")
        
        # DNI del cliente
        payer_identification = payer.get("identification", {})
        card_identification = raw_data.get("card", {}).get("cardholder", {}).get("identification", {})
        customer_dni = card_identification.get("number") or payer_identification.get("number")
        
        if not customer_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo extraer el email del cliente de los datos del pago"
            )
        
        # Extraer items del pago
        items_data = additional_info.get("items", [])
        
        if not items_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se encontraron items en los datos del pago"
            )
        
        # Buscar o crear usuario
        user = db.query(User).filter(User.email == customer_email).first()
        if not user:
            user = User(
                email=customer_email,
                full_name=customer_name,
                hashed_password=None
            )
            db.add(user)
            db.flush()
        
        # Generar número de orden único
        def generate_order_number():
            chars = string.ascii_uppercase + string.digits
            random_code = ''.join(secrets.choice(chars) for _ in range(6))
            return f"GEPE-{random_code}"
        
        order_number = generate_order_number()
        while db.query(Order).filter(Order.order_number == order_number).first():
            order_number = generate_order_number()
        
        # Calcular total desde los items
        total_amount = payment.transaction_amount
        
        # Crear la orden
        order = Order(
            user_id=user.id,
            order_number=order_number,
            status="PAID",  # Ya está pagado
            total_amount=total_amount,
            external_reference=raw_data.get("external_reference"),
            payment_id=mp_payment_id,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_phone=None,  # No disponible en raw_data
            customer_dni=customer_dni,
            shipping_method=None,  # No disponible, el cliente deberá proporcionar
            shipping_address=None,
            shipping_city=None,
            shipping_province=None,
            production_status=PRODUCTION_STATUS_WAITING_FABRIC
        )
        
        db.add(order)
        db.flush()
        
        # Crear los items de la orden
        for item_data in items_data:
            # Parsear descripción para extraer calidad y talle
            description = item_data.get("description", "")
            product_size = None
            
            # Intentar extraer talle de la descripción (formato: "Calidad: X - Talle: Y")
            if "Talle:" in description:
                try:
                    talle_part = description.split("Talle:")[1].strip()
                    product_size = talle_part.split()[0] if talle_part else None
                except:
                    pass
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=int(item_data.get("id", 0)) if item_data.get("id") else None,
                product_name=item_data.get("title", "Producto"),
                product_size=product_size,
                quantity=int(item_data.get("quantity", 1)),
                unit_price=float(item_data.get("unit_price", 0))
            )
            db.add(order_item)
        
        # Vincular el Payment a la Order
        payment.order_id = order.id
        
        db.commit()
        db.refresh(order)
        
        logger.info(f"✅ Orden {order_number} recuperada desde pago {mp_payment_id}")
        
        # Intentar enviar email de confirmación
        email_sent = False
        try:
            # Recargar orden con items
            order_with_items = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
            if order_with_items:
                email_sent = await send_order_confirmation_email(order_with_items)
                if email_sent:
                    order.confirmation_email_sent = True
                    db.commit()
                    logger.info(f"✅ Email de confirmación enviado a {customer_email}")
        except Exception as email_error:
            logger.warning(f"No se pudo enviar email de confirmación: {str(email_error)}")
        
        return {
            "success": True,
            "message": f"Orden recuperada exitosamente",
            "order_number": order_number,
            "order_id": order.id,
            "customer_email": customer_email,
            "customer_name": customer_name,
            "total_amount": total_amount,
            "items_count": len(items_data),
            "email_sent": email_sent,
            "note": "IMPORTANTE: Esta orden no tiene datos de envío. Contactar al cliente para obtenerlos."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error al recuperar orden desde pago: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al recuperar la orden: {str(e)}"
        )
