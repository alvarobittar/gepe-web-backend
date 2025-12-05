"""
Servicio de Email usando Resend
Documentación: https://resend.com/docs
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Intentar importar resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    RESEND_AVAILABLE = False
    logger.warning("Módulo 'resend' no instalado. Instalar con: pip install resend")


def _get_resend_api_key() -> Optional[str]:
    """Obtiene la API key de Resend desde las variables de entorno"""
    return os.getenv("RESEND_API_KEY")


def _is_email_service_configured() -> bool:
    """Verifica si el servicio de email está configurado correctamente"""
    if not RESEND_AVAILABLE:
        return False
    api_key = _get_resend_api_key()
    if not api_key:
        logger.warning("RESEND_API_KEY no configurada en variables de entorno")
        return False
    return True


async def send_production_complete_email(order) -> bool:
    """
    Envía un email al cliente notificando que su pedido está listo.
    
    Args:
        order: Objeto Order con los datos del pedido
        
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará notificación")
        return False
    
    if not order.customer_email:
        logger.warning(f"Orden {order.id} no tiene email de cliente")
        return False
    
    try:
        resend.api_key = _get_resend_api_key()
        
        # Preparar lista de productos
        products_html = ""
        for item in order.items:
            size_text = f" (Talle: {item.product_size})" if item.product_size else ""
            products_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{item.product_name}{size_text}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: center;">{item.quantity}</td>
            </tr>
            """
        
        # HTML del email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">¡Tu pedido está listo! 🎉</h1>
            </div>
            
            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px;">Hola <strong>{order.customer_name or 'Cliente'}</strong>,</p>
                
                <p>¡Excelentes noticias! Tu pedido <strong style="color: #667eea;">{order.order_number}</strong> ya está terminado y listo para ser enviado.</p>
                
                <div style="background: #f9fafb; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h3 style="margin-top: 0; color: #374151;">Productos en tu pedido:</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #e5e7eb;">
                                <th style="padding: 10px; text-align: left;">Producto</th>
                                <th style="padding: 10px; text-align: center;">Cantidad</th>
                            </tr>
                        </thead>
                        <tbody>
                            {products_html}
                        </tbody>
                    </table>
                </div>
                
                <p style="font-size: 14px; color: #6b7280;">
                    Te enviaremos otro correo con la información de seguimiento cuando tu pedido sea despachado.
                </p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    ¿Tenés alguna pregunta? Respondé a este correo o contactanos por WhatsApp.
                </p>
            </div>
            
            <p style="text-align: center; font-size: 12px; color: #9ca3af; margin-top: 20px;">
                © 2024 GEPE - Indumentaria Deportiva
            </p>
        </body>
        </html>
        """
        
        # Enviar email
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepe.com.ar>"),
            "to": [order.customer_email],
            "subject": f"🎉 ¡Tu pedido {order.order_number} está listo!",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        
        logger.info(f"Email enviado exitosamente a {order.customer_email}. ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar email: {str(e)}", exc_info=True)
        return False


async def send_order_shipped_email(order, tracking_code: str = None) -> bool:
    """
    Envía un email al cliente notificando que su pedido fue despachado.
    
    Args:
        order: Objeto Order con los datos del pedido
        tracking_code: Código de seguimiento del envío (opcional)
        
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará notificación")
        return False
    
    if not order.customer_email:
        logger.warning(f"Orden {order.id} no tiene email de cliente")
        return False
    
    try:
        resend.api_key = _get_resend_api_key()
        
        tracking_section = ""
        if tracking_code:
            tracking_section = f"""
            <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center;">
                <p style="margin: 0; color: #065f46;">
                    <strong>Código de seguimiento:</strong><br>
                    <span style="font-size: 18px; font-weight: bold; color: #10b981;">{tracking_code}</span>
                </p>
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">¡Tu pedido está en camino! 📦</h1>
            </div>
            
            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px;">Hola <strong>{order.customer_name or 'Cliente'}</strong>,</p>
                
                <p>Tu pedido <strong style="color: #10b981;">{order.order_number}</strong> ya fue despachado y está en camino.</p>
                
                {tracking_section}
                
                <p style="font-size: 14px; color: #6b7280;">
                    Podés seguir el estado de tu envío con el código de seguimiento.
                </p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    ¿Tenés alguna pregunta? Respondé a este correo o contactanos por WhatsApp.
                </p>
            </div>
            
            <p style="text-align: center; font-size: 12px; color: #9ca3af; margin-top: 20px;">
                © 2024 GEPE - Indumentaria Deportiva
            </p>
        </body>
        </html>
        """
        
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepe.com.ar>"),
            "to": [order.customer_email],
            "subject": f"📦 Tu pedido {order.order_number} está en camino",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        
        logger.info(f"Email de envío enviado a {order.customer_email}. ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar email de envío: {str(e)}", exc_info=True)
        return False
