"""
Router para gestionar pagos con Mercado Pago Checkout Pro
"""
import logging
import mercadopago
from fastapi import APIRouter, HTTPException, Request, Depends, status
from sqlalchemy.orm import Session
from typing import Dict, Any

import json
from ..config import get_settings
from ..database import get_db
from ..models.order import Order, PRODUCTION_STATUS_WAITING_FABRIC
from ..models.payment import Payment
from ..schemas.payment_schema import PreferenceInput, PreferenceResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payments"])


@router.get("/config-status")
async def check_mp_config():
    """
    Endpoint de debugging para verificar si MP_ACCESS_TOKEN está configurado
    """
    settings = get_settings()
    return {
        "mp_access_token_configured": bool(settings.mp_access_token),
        "mp_access_token_length": len(settings.mp_access_token) if settings.mp_access_token else 0,
        "mp_webhook_url_configured": bool(settings.mp_webhook_url),
        "cors_origin": settings.cors_origin
    }


def get_mp_sdk():
    """
    Retorna una instancia del SDK de Mercado Pago configurado
    """
    settings = get_settings()  # Obtener settings cada vez para evitar problemas de cache
    if not settings.mp_access_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MP_ACCESS_TOKEN no configurado. Revisar archivo .env"
        )
    
    sdk = mercadopago.SDK(settings.mp_access_token)
    return sdk


@router.post("/create_preference", response_model=PreferenceResponse)
async def create_preference(
    preference_input: PreferenceInput,
    db: Session = Depends(get_db)
):
    """
    Crea una preferencia de pago en Mercado Pago para Checkout Pro.
    
    IMPORTANTE: Rapipago y PagoFácil estarán disponibles por defecto (NO se excluyen).
    
    Args:
        preference_input: Datos de la preferencia (items, payer, etc)
        db: Sesión de base de datos
        
    Returns:
        PreferenceResponse con init_point (URL de pago)
    """
    try:
        settings = get_settings()  # Obtener settings cada vez
        sdk = get_mp_sdk()
        
        # Validar que cors_origin esté configurado
        cors_origin = settings.cors_origin
        if not cors_origin or cors_origin.strip() == "":
            cors_origin = "http://localhost:3000"
            logger.warning("CORS_ORIGIN no configurado o vacío, usando http://localhost:3000 por defecto")
        
        # Asegurarse de que cors_origin no termine con /
        cors_origin = cors_origin.rstrip('/')
        
        # Construir URLs de retorno (Mercado Pago requiere URLs absolutas válidas)
        success_url = f"{cors_origin}/checkout/success"
        failure_url = f"{cors_origin}/checkout/failure"
        pending_url = f"{cors_origin}/checkout/pending"
        
        # Validar que las URLs sean válidas
        if not success_url.startswith(('http://', 'https://')):
            logger.error(f"URL de success inválida: {success_url}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"URL de retorno inválida. CORS_ORIGIN debe ser una URL completa (ej: http://localhost:3000)"
            )
        
        # Detectar si estamos en desarrollo local o producción
        # Si es localhost o 127.0.0.1, NO usar auto_return (MP lo rechaza)
        # Si es ngrok o cualquier URL pública (https://), SÍ usar auto_return
        is_localhost = "localhost" in cors_origin or "127.0.0.1" in cors_origin
        is_public_url = cors_origin.startswith("https://") or "ngrok" in cors_origin.lower()
        
        logger.info(f"🔗 CORS_ORIGIN leído del .env: {cors_origin}")
        logger.info(f"URLs de retorno configuradas - success: {success_url}, failure: {failure_url}, pending: {pending_url}")
        if is_localhost:
            logger.info("Entorno detectado: Desarrollo (localhost) - auto_return deshabilitado")
        elif is_public_url:
            logger.info("Entorno detectado: Desarrollo con ngrok/URL pública - auto_return habilitado")
        else:
            logger.info("Entorno detectado: Producción - auto_return habilitado")
        
        # Construir el objeto de preferencia para Mercado Pago
        preference_data = {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description or item.title,
                    "picture_url": item.picture_url,
                    "category_id": item.category_id or "clothing",
                    "quantity": item.quantity,
                    "currency_id": item.currency_id,
                    "unit_price": float(item.unit_price)
                }
                for item in preference_input.items
            ],
            "payer": {
                "email": preference_input.payer.email,
            },
            "back_urls": {
                "success": success_url,
                "failure": failure_url,
                "pending": pending_url
            },
            "statement_descriptor": "GEPE SPORTS",
            "external_reference": preference_input.external_reference or "",
        }
        
        # Agregar nombre y apellido si están disponibles
        if preference_input.payer.first_name:
            preference_data["payer"]["name"] = preference_input.payer.first_name
        if preference_input.payer.last_name:
            preference_data["payer"]["surname"] = preference_input.payer.last_name
            
        # Agregar identificación si está disponible (para factura futura)
        if preference_input.payer.identification:
            preference_data["payer"]["identification"] = {
                "type": preference_input.payer.identification.type,
                "number": preference_input.payer.identification.number
            }
        
        # Configurar URL de notificaciones (Webhook)
        if settings.mp_webhook_url:
            preference_data["notification_url"] = settings.mp_webhook_url
        elif preference_input.notification_url:
            preference_data["notification_url"] = preference_input.notification_url
            
        # IMPORTANTE: NO excluimos payment_methods para permitir Rapipago
        # Si se necesita excluir algún método específico, se puede hacer así:
        # preference_data["payment_methods"] = {
        #     "excluded_payment_types": [],  # No excluir tipos de pago
        #     "excluded_payment_methods": []  # No excluir métodos específicos
        # }
        
        # Solo usar auto_return con URLs públicas (ngrok o producción)
        # En localhost, MP no puede validar las URLs y rechaza la preferencia
        if is_public_url:
            preference_data["auto_return"] = "approved"
            logger.info("✅ auto_return habilitado (URL pública - ngrok o producción)")
        else:
            logger.info("⚠️ auto_return deshabilitado (localhost - el usuario debe hacer click en 'Volver al sitio')")
        
        logger.info(f"Creando preferencia de MP para {preference_input.payer.email}")
        logger.info(f"back_urls configuradas: {preference_data.get('back_urls')}")
        logger.info(f"auto_return configurado: {preference_data.get('auto_return', 'NO CONFIGURADO')}")
        
        # Verificar que back_urls tenga success definido
        if "back_urls" not in preference_data or "success" not in preference_data["back_urls"]:
            logger.error("ERROR: back_urls.success no está definido en preference_data")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de configuración: back_urls.success no está definido"
            )
        
        logger.debug(f"Datos de preferencia completos: {preference_data}")
        
        # Crear la preferencia en Mercado Pago
        preference_response = sdk.preference().create(preference_data)
        
        if preference_response["status"] != 201:
            logger.error(f"Error al crear preferencia: {preference_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al crear preferencia en Mercado Pago: {preference_response.get('response', {})}"
            )
        
        preference = preference_response["response"]
        
        # Opcional: Guardar la orden en la BD con status 'PENDING'
        # Puedes descomentar esto si quieres trackear la orden desde el inicio
        # order = Order(
        #     user_id=None,  # O el ID del usuario si está logueado
        #     status="PENDING",
        #     total_amount=sum(item.unit_price * item.quantity for item in preference_input.items),
        #     external_reference=preference_input.external_reference
        # )
        # db.add(order)
        # db.commit()
        
        logger.info(f"Preferencia creada exitosamente: {preference['id']}")
        
        return PreferenceResponse(
            init_point=preference["init_point"],
            preference_id=preference["id"],
            sandbox_init_point=preference.get("sandbox_init_point")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado al crear preferencia: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al procesar la solicitud: {str(e)}"
        )


@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Endpoint para recibir notificaciones de Mercado Pago (Webhooks).
    
    IMPORTANTE: Este endpoint debe responder siempre con 200 OK a Mercado Pago.
    
    Lógica de negocio:
    - Recibe notificación de MP con id y topic/type
    - NO confía en el body, consulta el pago real usando SDK
    - Actualiza el estado de la orden en la BD según el status real
    
    Estados de pago de MP:
    - approved: Pago aprobado
    - pending: Pago pendiente (ej: Rapipago aún no pagado)
    - rejected: Pago rechazado
    - cancelled: Pago cancelado
    - refunded: Pago reembolsado
    - charged_back: Contracargo
    """
    try:
        # Obtener parámetros de query
        params = dict(request.query_params)
        topic = params.get("topic") or params.get("type")
        resource_id = params.get("id") or params.get("data.id")
        
        logger.info(f"Webhook recibido - Topic: {topic}, ID: {resource_id}")
        logger.debug(f"Query params completos: {params}")
        
        # Solo procesamos notificaciones de pagos
        if topic != "payment":
            logger.info(f"Topic '{topic}' ignorado. Solo procesamos 'payment'")
            return {"status": "ignored", "reason": f"Topic {topic} no procesado"}
        
        if not resource_id:
            logger.warning("No se recibió ID del recurso en la notificación")
            return {"status": "error", "reason": "Missing resource ID"}
        
        # CRÍTICO: Consultar el pago real usando el SDK (NO confiar en el body)
        sdk = get_mp_sdk()
        payment_response = sdk.payment().get(resource_id)
        
        if payment_response["status"] != 200:
            logger.error(f"Error al obtener pago {resource_id}: {payment_response}")
            return {"status": "error", "reason": "Could not fetch payment from MP"}
        
        payment = payment_response["response"]
        payment_status = payment.get("status")
        external_reference = payment.get("external_reference")
        
        logger.info(
            f"Pago {resource_id} - Status: {payment_status}, "
            f"Referencia: {external_reference}, "
            f"Monto: {payment.get('transaction_amount')}"
        )
        
        # Guardar o actualizar información detallada del pago en la tabla payments
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
            f"Información de método de pago extraída - "
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
        from datetime import datetime as dt
        date_created_str = payment.get("date_created")
        date_approved_str = payment.get("date_approved")
        date_last_updated_str = payment.get("date_last_updated")
        
        date_created = dt.fromisoformat(date_created_str.replace("Z", "+00:00")) if date_created_str else None
        date_approved = dt.fromisoformat(date_approved_str.replace("Z", "+00:00")) if date_approved_str else None
        date_last_updated = dt.fromisoformat(date_last_updated_str.replace("Z", "+00:00")) if date_last_updated_str else None
        
        # Buscar o crear registro de Payment
        existing_payment = db.query(Payment).filter(Payment.mp_payment_id == resource_id).first()
        
        if existing_payment:
            # Actualizar pago existente
            existing_payment.status = payment_status
            existing_payment.status_detail = payment.get("status_detail")
            existing_payment.transaction_amount = float(payment.get("transaction_amount", 0))
            existing_payment.currency_id = payment.get("currency_id", "ARS")
            existing_payment.payment_method_id = payment_method_id
            existing_payment.payment_type_id = payment_type_id
            existing_payment.card_last_four_digits = card_last_four
            existing_payment.card_holder_name = card_holder
            existing_payment.refunded_amount = refunded_amount
            existing_payment.refunded_count = refunded_count
            existing_payment.has_chargeback = has_chargeback
            if date_created:
                existing_payment.date_created = date_created
            if date_approved:
                existing_payment.date_approved = date_approved
            if date_last_updated:
                existing_payment.date_last_updated = date_last_updated
            existing_payment.mp_raw_data = json.dumps(payment)
            db_payment = existing_payment
        else:
            # Crear nuevo registro de Payment
            order_id = None
            if external_reference:
                order = db.query(Order).filter(Order.external_reference == external_reference).first()
                if order:
                    order_id = order.id
            
            db_payment = Payment(
                order_id=order_id,
                mp_payment_id=resource_id,
                transaction_amount=float(payment.get("transaction_amount", 0)),
                currency_id=payment.get("currency_id", "ARS"),
                payment_method_id=payment_method_id,
                payment_type_id=payment_type_id,
                card_last_four_digits=card_last_four,
                card_holder_name=card_holder,
                status=payment_status,
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
        
        # Lógica de actualización de orden según status del pago
        if external_reference:
            # Buscar la orden por external_reference
            order = db.query(Order).filter(Order.external_reference == external_reference).first()
            
            if not order:
                logger.warning(f"No se encontró orden con external_reference: {external_reference}")
                logger.info("La orden puede ser creada desde el frontend al recibir la confirmación")
            else:
                # Actualizar order_id en el payment si no estaba asignado
                if not db_payment.order_id:
                    db_payment.order_id = order.id
                
                # Actualizar el estado de la orden según el payment_status
                if payment_status == "approved":
                    logger.info(f"✅ Pago APROBADO para orden {external_reference}")
                    order.status = "PAID"
                    order.payment_id = resource_id
                    # Auto-asignar estado de producción al pasar a PAID
                    order.production_status = PRODUCTION_STATUS_WAITING_FABRIC
                    db.commit()
                    logger.info(f"Orden {order.id} actualizada a PAID con production_status=WAITING_FABRIC")
                    
                    # Enviar email de confirmación al cliente (solo si no se ha enviado antes)
                    if not order.confirmation_email_sent:
                        try:
                            from sqlalchemy.orm import joinedload
                            from ..services.email_service import send_order_confirmation_email
                            # Recargar la orden con los items para el email
                            order_with_items = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
                            if order_with_items:
                                email_sent = await send_order_confirmation_email(order_with_items)
                                if email_sent:
                                    # Marcar como enviado para no duplicar
                                    order.confirmation_email_sent = True
                                    db.commit()
                                    logger.info(f"✅ Email de confirmación enviado a {order.customer_email}")
                                else:
                                    logger.warning(f"⚠️ No se pudo enviar email de confirmación a {order.customer_email}")
                        except Exception as email_error:
                            # No bloquear el webhook si falla el email
                            logger.error(f"Error al enviar email de confirmación: {str(email_error)}")
                    
                elif payment_status == "pending":
                    logger.info(f"⏳ Pago PENDIENTE para orden {external_reference} (puede ser Rapipago)")
                    order.status = "PENDING"
                    order.payment_id = resource_id
                    db.commit()
                    logger.info(f"Orden {order.id} mantenida en PENDING")
                    
                elif payment_status == "rejected":
                    logger.info(f"❌ Pago RECHAZADO para orden {external_reference}")
                    order.status = "CANCELLED"
                    order.payment_id = resource_id
                    db.commit()
                    logger.info(f"Orden {order.id} actualizada a CANCELLED")
                    
                elif payment_status == "cancelled":
                    logger.info(f"🚫 Pago CANCELADO para orden {external_reference}")
                    order.status = "CANCELLED"
                    order.payment_id = resource_id
                    db.commit()
                    logger.info(f"Orden {order.id} actualizada a CANCELLED")
                    
                else:
                    logger.warning(f"Status desconocido: {payment_status} para orden {external_reference}")
        else:
            logger.warning("No se recibió external_reference en el pago")
        
        # Commit de los cambios en Payment
        db.commit()
        logger.info(f"Payment {resource_id} guardado/actualizado en BD")
        
        # SIEMPRE retornar 200 OK a Mercado Pago
        return {"status": "ok"}
        
    except Exception as e:
        # Incluso con error, retornamos 200 para que MP deje de reintentar
        logger.error(f"Error procesando webhook: {str(e)}", exc_info=True)
        return {"status": "error", "detail": str(e)}

