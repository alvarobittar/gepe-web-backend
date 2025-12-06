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
