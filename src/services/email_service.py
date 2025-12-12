"""
Servicio de Email usando Resend
Documentación: https://resend.com/docs
"""
import os
import logging
from typing import Optional, List

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


def _get_default_reply_to() -> Optional[str]:
    """Reply-To por defecto para correos salientes"""
    return os.getenv("RESEND_REPLY_TO") or os.getenv("DEFAULT_NOTIFICATION_EMAIL")


def _is_email_service_configured() -> bool:
    """Verifica si el servicio de email está configurado correctamente"""
    if not RESEND_AVAILABLE:
        return False
    api_key = _get_resend_api_key()
    if not api_key:
        logger.warning("RESEND_API_KEY no configurada en variables de entorno")
        return False
    return True


def is_email_service_configured() -> bool:
    """Función pública para verificar si el servicio de email está configurado"""
    return _is_email_service_configured()


def get_email_config_info() -> dict:
    """Obtiene información sobre la configuración del servicio de email"""
    return {
        "resend_available": RESEND_AVAILABLE,
        "api_key_configured": bool(_get_resend_api_key()),
        "from_email": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
        "configured": _is_email_service_configured()
    }


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
        
        # Versión plain text para mejor deliverability
        products_text = ""
        for item in order.items:
            size_text = f" (Talle: {item.product_size})" if item.product_size else ""
            products_text += f"  - {item.product_name}{size_text} x{item.quantity}\n"
        
        text_content = f"""
Tu pedido está listo

Hola {order.customer_name or 'Cliente'},

¡Excelentes noticias! Tu pedido {order.order_number} ya está terminado y listo para ser enviado.

Productos en tu pedido:
{products_text}
Te enviaremos otro correo con la información de seguimiento cuando tu pedido sea despachado.

¿Tenés alguna pregunta? Respondé a este correo o contactanos por WhatsApp.

---
GEPE - Indumentaria Deportiva
        """
        
        # Enviar email
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": [order.customer_email],
            "subject": f"Tu pedido {order.order_number} esta listo!",
            "html": html_content,
            "text": text_content,
        }

        reply_to = _get_default_reply_to()
        if reply_to:
            params["reply_to"] = [reply_to]
        
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
            # Obtener empresa y sucursal del objeto order
            tracking_company = getattr(order, 'tracking_company', None) or ""
            tracking_branch = getattr(order, 'tracking_branch_address', None) or ""
            
            company_html = f"""
                <p style="margin: 5px 0; color: #065f46;">
                    <strong>Empresa:</strong> {tracking_company}
                </p>
            """ if tracking_company else ""
            
            branch_html = f"""
                <p style="margin: 5px 0; color: #065f46; font-size: 14px;">
                    <strong>Sucursal:</strong> {tracking_branch}
                </p>
            """ if tracking_branch else ""
            
            tracking_section = f"""
            <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center;">
                <p style="margin: 0 0 10px 0; color: #065f46;">
                    <strong>Código de seguimiento:</strong><br>
                    <span style="font-size: 18px; font-weight: bold; color: #10b981;">{tracking_code}</span>
                </p>
                {company_html}
                {branch_html}
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
        
        # Versión plain text
        tracking_company = getattr(order, 'tracking_company', None) or ""
        tracking_branch = getattr(order, 'tracking_branch_address', None) or ""
        
        tracking_text = ""
        if tracking_code:
            tracking_text = f"\nCódigo de seguimiento: {tracking_code}"
            if tracking_company:
                tracking_text += f"\nEmpresa: {tracking_company}"
            if tracking_branch:
                tracking_text += f"\nSucursal: {tracking_branch}"
            tracking_text += "\n"
        
        text_content = f"""
Tu pedido esta en camino

Hola {order.customer_name or 'Cliente'},

Tu pedido {order.order_number} ya fue despachado y está en camino.
{tracking_text}
Podés seguir el estado de tu envío con el código de seguimiento.

¿Tenés alguna pregunta? Respondé a este correo o contactanos por WhatsApp.

---
GEPE - Indumentaria Deportiva
        """
        
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": [order.customer_email],
            "subject": f"Tu pedido {order.order_number} esta en camino",
            "html": html_content,
            "text": text_content,
        }

        reply_to = _get_default_reply_to()
        if reply_to:
            params["reply_to"] = [reply_to]
        
        response = resend.Emails.send(params)
        
        logger.info(f"Email de envío enviado a {order.customer_email}. ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar email de envío: {str(e)}", exc_info=True)
        return False


async def send_test_email(email: str) -> bool:
    """
    Envía un correo de prueba/verificación al correo especificado.
    Se usa para verificar que el correo funciona correctamente cuando se agrega.
    
    Args:
        email: Dirección de correo electrónico a la que enviar el email de prueba
        
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará email de prueba")
        return False
    
    if not email or not email.strip():
        logger.warning("Email vacío, no se enviará email de prueba")
        return False
    
    try:
        resend.api_key = _get_resend_api_key()
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Correo de prueba recibido</h1>
            </div>
            
            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px;">¡Perfecto!</p>
                
                <p>Este es un correo de prueba para verificar que tu dirección de correo electrónico está configurada correctamente para recibir notificaciones del sistema de GEPE.</p>
                
                <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0; color: #065f46;">
                        <strong>✅ Verificación exitosa</strong><br>
                        <span style="font-size: 14px;">A partir de ahora, recibirás notificaciones sobre eventos importantes como nuevas ventas, pagos recibidos y stock bajo.</span>
                    </p>
                </div>
                
                <p style="font-size: 14px; color: #6b7280;">
                    No necesitas realizar ninguna acción. Este correo solo confirma que las notificaciones están funcionando correctamente.
                </p>
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    Sistema de Notificaciones GEPE
                </p>
            </div>
            
            <p style="text-align: center; font-size: 12px; color: #9ca3af; margin-top: 20px;">
                © 2025 GEPE - Indumentaria Deportiva
            </p>
        </body>
        </html>
        """
        
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": [email.strip()],
            "subject": "✅ Correo de prueba - Notificaciones GEPE",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        
        logger.info(f"Email de prueba enviado exitosamente a {email}. ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar email de prueba: {str(e)}", exc_info=True)
        return False


async def send_regret_notification_email(form_data: dict, admin_emails: List[str]) -> bool:
    """
    Envía email de arrepentimiento de compra a los admin emails configurados.
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará notificación de arrepentimiento")
        return False

    if not admin_emails:
        logger.warning("No hay emails de administradores configurados para recibir notificaciones")
        return False

    try:
        resend.api_key = _get_resend_api_key()

        cliente_nombre = f"{form_data.get('nombre','').strip()} {form_data.get('apellido','').strip()}".strip()
        numero_pedido = form_data.get("numeroPedido") or "No especificado"
        articulos = form_data.get("articulosComprados") or "No especificado"
        telefono = form_data.get("telefono") or "No especificado"
        correo = form_data.get("correo") or "No especificado"
        dni = form_data.get("dni") or "No especificado"
        ciudad = form_data.get("ciudad") or "No especificada"
        motivo = form_data.get("motivo") or "No especificado"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; max-width: 640px; margin: 0 auto; padding: 24px; background: #f9fafb;">
            <div style="background: #111827; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 22px;">🛑 Arrepentimiento de compra</h1>
            </div>
            <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="margin: 0 0 12px 0;">Se recibió una solicitud de arrepentimiento de compra.</p>
                <h3 style="margin: 16px 0 8px 0; color: #111827;">Datos del cliente</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 6px 0; color: #6b7280;">Nombre</td><td style="padding: 6px 0; font-weight: 600;">{cliente_nombre or 'No especificado'}</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">DNI</td><td style="padding: 6px 0; font-weight: 600;">{dni}</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Ciudad</td><td style="padding: 6px 0; font-weight: 600;">{ciudad}</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Teléfono</td><td style="padding: 6px 0; font-weight: 600;">{telefono}</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Correo</td><td style="padding: 6px 0; font-weight: 600;">{correo}</td></tr>
                </table>

                <h3 style="margin: 16px 0 8px 0; color: #111827;">Detalle de la compra</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 6px 0; color: #6b7280;">N° Pedido</td><td style="padding: 6px 0; font-weight: 600;">{numero_pedido}</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Artículos</td><td style="padding: 6px 0; font-weight: 600;">{articulos}</td></tr>
                </table>

                <h3 style="margin: 16px 0 8px 0; color: #111827;">Motivo</h3>
                <div style="padding: 12px; background: #f3f4f6; border-radius: 8px; color: #374151;">{motivo}</div>
            </div>
            <p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 12px;">GEPE Notificaciones</p>
        </body>
        </html>
        """

        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": admin_emails,
            "subject": f"🛑 Arrepentimiento de compra - Pedido {numero_pedido}",
            "html": html_content,
        }
        resend.Emails.send(params)
        logger.info("Email de arrepentimiento enviado a admins")
        return True
    except Exception as e:
        logger.error(f"Error al enviar email de arrepentimiento: {e}", exc_info=True)
        return False


async def send_sale_notification_email(order, admin_emails: List[str]) -> bool:
    """
    Envía un email de notificación a los administradores cuando se realiza una venta.
    
    Args:
        order: Objeto Order con los datos del pedido
        admin_emails: Lista de correos electrónicos de administradores verificados
        
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará notificación de venta")
        return False
    
    if not admin_emails:
        logger.warning("No hay emails de administradores configurados para recibir notificaciones")
        return False
    
    try:
        resend.api_key = _get_resend_api_key()
        
        # Preparar lista de productos
        products_html = ""
        total_items = 0
        for item in order.items:
            size_text = f" (Talle: {item.product_size})" if item.product_size else ""
            price_formatted = f"${item.unit_price:,.0f}".replace(",", ".")
            subtotal = item.unit_price * item.quantity
            subtotal_formatted = f"${subtotal:,.0f}".replace(",", ".")
            products_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.product_name}{size_text}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">{item.quantity}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{price_formatted}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{subtotal_formatted}</td>
            </tr>
            """
            total_items += item.quantity
        
        # Formatear total
        total_formatted = f"${order.total_amount:,.0f}".replace(",", ".")
        
        # Información de envío
        shipping_info = ""
        if order.shipping_method:
            shipping_method_text = "Envío a domicilio" if order.shipping_method == "domicilio" else "Retiro en local"
            shipping_info = f"""
            <div style="margin-top: 15px; padding: 15px; background: #f3f4f6; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0; color: #374151;">📦 Envío</h4>
                <p style="margin: 0; color: #6b7280;"><strong>Método:</strong> {shipping_method_text}</p>
            """
            if order.shipping_address:
                shipping_info += f'<p style="margin: 5px 0 0 0; color: #6b7280;"><strong>Dirección:</strong> {order.shipping_address}</p>'
            if order.shipping_city:
                shipping_info += f'<p style="margin: 5px 0 0 0; color: #6b7280;"><strong>Ciudad:</strong> {order.shipping_city}</p>'
            shipping_info += "</div>"
        
        # HTML del email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">💰 ¡Nueva Venta Realizada!</h1>
            </div>
            
            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 15px; margin-bottom: 20px; text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #065f46;">Pedido</p>
                    <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #10b981;">{order.order_number}</p>
                </div>
                
                <h3 style="margin-top: 0; color: #374151; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">👤 Datos del Cliente</h3>
                <table style="width: 100%; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 5px 0; color: #6b7280;">Nombre:</td>
                        <td style="padding: 5px 0; font-weight: 600;">{order.customer_name or 'No especificado'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0; color: #6b7280;">Email:</td>
                        <td style="padding: 5px 0; font-weight: 600;">{order.customer_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0; color: #6b7280;">Teléfono:</td>
                        <td style="padding: 5px 0; font-weight: 600;">{order.customer_phone or 'No especificado'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0; color: #6b7280;">DNI:</td>
                        <td style="padding: 5px 0; font-weight: 600;">{order.customer_dni or 'No especificado'}</td>
                    </tr>
                </table>
                
                <h3 style="color: #374151; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">🛒 Productos ({total_items} items)</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <thead>
                        <tr style="background: #f9fafb;">
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151;">Producto</th>
                            <th style="padding: 10px; text-align: center; font-weight: 600; color: #374151;">Cant.</th>
                            <th style="padding: 10px; text-align: right; font-weight: 600; color: #374151;">Precio</th>
                            <th style="padding: 10px; text-align: right; font-weight: 600; color: #374151;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {products_html}
                    </tbody>
                    <tfoot>
                        <tr style="background: #10b981; color: white;">
                            <td colspan="3" style="padding: 12px; font-weight: bold; font-size: 16px;">TOTAL</td>
                            <td style="padding: 12px; text-align: right; font-weight: bold; font-size: 18px;">{total_formatted}</td>
                        </tr>
                    </tfoot>
                </table>
                
                {shipping_info}
                
                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                
                <p style="font-size: 12px; color: #9ca3af; text-align: center;">
                    Este es un email automático del sistema de notificaciones de GEPE.
                </p>
            </div>
            
            <p style="text-align: center; font-size: 12px; color: #9ca3af; margin-top: 20px;">
                © 2024 GEPE - Indumentaria Deportiva
            </p>
        </body>
        </html>
        """
        
        # Enviar email a todos los administradores
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": admin_emails,
            "subject": f"💰 Nueva Venta: {order.order_number} - {total_formatted}",
            "html": html_content,
        }
        
        response = resend.Emails.send(params)
        
        logger.info(f"✅ Notificación de venta enviada a {len(admin_emails)} administradores. Orden: {order.order_number}, ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar notificación de venta: {str(e)}", exc_info=True)
        return False


async def send_contact_email(form_data: dict, admin_emails: List[str]) -> bool:
    """
    Envía el mensaje del formulario de Contacto a los correos de admins.
    Usa el correo del cliente como Reply-To para que puedan responderle directo.
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará contacto")
        return False

    if not admin_emails:
        logger.warning("No hay emails de administradores configurados para recibir contacto")
        return False

    try:
        resend.api_key = _get_resend_api_key()

        nombre = form_data.get("nombre", "").strip() or "Sin nombre"
        email = form_data.get("email", "").strip()
        mensaje = form_data.get("mensaje", "").strip()

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; max-width: 640px; margin: 0 auto; padding: 24px; background: #f9fafb;">
            <div style="background: #0f172a; color: white; padding: 20px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="margin: 0; font-size: 20px;">📨 Nuevo mensaje de contacto</h1>
            </div>
            <div style="background: white; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <h3 style="margin: 0 0 12px 0; color: #111827;">Datos</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
                    <tr><td style="padding: 6px 0; color: #6b7280;">Nombre</td><td style="padding: 6px 0; font-weight: 600;">{nombre}</td></tr>
                    <tr><td style="padding: 6px 0; color: #6b7280;">Email</td><td style="padding: 6px 0; font-weight: 600;">{email or 'No provisto'}</td></tr>
                </table>
                <h3 style="margin: 0 0 8px 0; color: #111827;">Mensaje</h3>
                <div style="padding: 12px; background: #f3f4f6; border-radius: 8px; color: #374151; white-space: pre-wrap;">{mensaje}</div>
            </div>
            <p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 12px;">GEPE Contacto</p>
        </body>
        </html>
        """

        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": admin_emails,
            "subject": f"📨 Contacto: {nombre}",
            "html": html_content,
        }

        if email:
            params["reply_to"] = [email]

        response = resend.Emails.send(params)
        logger.info(f"Email de contacto enviado a {len(admin_emails)} admins. ID: {response.get('id', 'N/A')}")
        return True
    except Exception as e:
        logger.error(f"Error al enviar email de contacto: {str(e)}", exc_info=True)
        return False


async def send_order_confirmation_email(order) -> bool:
    """
    Envía un email de confirmación de compra al cliente cuando su pago es aprobado.
    
    Args:
        order: Objeto Order con los datos del pedido
        
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    """
    if not _is_email_service_configured():
        logger.warning("Servicio de email no configurado, no se enviará confirmación de compra")
        return False
    
    if not order.customer_email:
        logger.warning(f"Orden {order.id} no tiene email de cliente")
        return False
    
    try:
        resend.api_key = _get_resend_api_key()
        
        # Preparar lista de productos
        products_html = ""
        total_items = 0
        for item in order.items:
            size_text = f" (Talle: {item.product_size})" if item.product_size else ""
            price_formatted = f"${item.unit_price:,.0f}".replace(",", ".")
            subtotal = item.unit_price * item.quantity
            subtotal_formatted = f"${subtotal:,.0f}".replace(",", ".")
            products_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{item.product_name}{size_text}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: center;">{item.quantity}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{price_formatted}</td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{subtotal_formatted}</td>
            </tr>
            """
            total_items += item.quantity
        
        # Formatear total
        total_formatted = f"${order.total_amount:,.0f}".replace(",", ".")
        
        # Información de envío
        shipping_info = ""
        if order.shipping_method:
            shipping_method_text = "Envío a domicilio" if order.shipping_method == "domicilio" else "Retiro en local"
            shipping_info = f"""
            <div style="margin-top: 20px; padding: 15px; background: #f0fdf4; border: 1px solid #10b981; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0; color: #065f46;">📦 Datos de envío</h4>
                <p style="margin: 0; color: #047857;"><strong>Método:</strong> {shipping_method_text}</p>
            """
            if order.shipping_address:
                shipping_info += f'<p style="margin: 5px 0 0 0; color: #047857;"><strong>Dirección:</strong> {order.shipping_address}</p>'
            if order.shipping_city:
                shipping_info += f'<p style="margin: 5px 0 0 0; color: #047857;"><strong>Ciudad:</strong> {order.shipping_city}</p>'
            if order.shipping_province:
                shipping_info += f'<p style="margin: 5px 0 0 0; color: #047857;"><strong>Provincia:</strong> {order.shipping_province}</p>'
            shipping_info += "</div>"
        
        # URL del sitio
        site_url = os.getenv("FRONTEND_URL", "https://gepesport.com")
        tracking_url = f"{site_url}/pedidos/{order.id}?email={order.customer_email}"
        
        # HTML del email
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ ¡Gracias por tu compra!</h1>
            </div>
            
            <div style="background: #ffffff; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
                <p style="font-size: 16px;">Hola <strong>{order.customer_name or 'Cliente'}</strong>,</p>
                
                <p>¡Gracias por elegirnos! Tu pago fue confirmado exitosamente y ya comenzamos a preparar tu pedido.</p>
                
                <div style="background: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 15px; margin: 20px 0; text-align: center;">
                    <p style="margin: 0; font-size: 14px; color: #065f46;">Número de pedido</p>
                    <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #10b981;">{order.order_number}</p>
                </div>
                
                <h3 style="color: #374151; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">🛒 Resumen de tu compra</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                    <thead>
                        <tr style="background: #f9fafb;">
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151;">Producto</th>
                            <th style="padding: 10px; text-align: center; font-weight: 600; color: #374151;">Cant.</th>
                            <th style="padding: 10px; text-align: right; font-weight: 600; color: #374151;">Precio</th>
                            <th style="padding: 10px; text-align: right; font-weight: 600; color: #374151;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {products_html}
                    </tbody>
                    <tfoot>
                        <tr style="background: #10b981; color: white;">
                            <td colspan="3" style="padding: 12px; font-weight: bold; font-size: 16px;">TOTAL</td>
                            <td style="padding: 12px; text-align: right; font-weight: bold; font-size: 18px;">{total_formatted}</td>
                        </tr>
                    </tfoot>
                </table>
                
                {shipping_info}
                
                <!-- Botón de seguimiento -->
                <div style="text-align: center; margin: 25px 0;">
                    <a href="{tracking_url}" style="display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px;">
                        📦 Ver estado de mi pedido
                    </a>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px;">
                    <h4 style="margin: 0 0 8px 0; color: #92400e;">⏱️ ¿Qué sigue?</h4>
                    <p style="margin: 0; font-size: 14px; color: #92400e;">
                        Tu pedido será confeccionado a medida. Te avisaremos por email cuando esté listo para ser enviado.
                    </p>
                </div>
                
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
        
        # Versión plain text
        products_text = ""
        for item in order.items:
            size_text = f" (Talle: {item.product_size})" if item.product_size else ""
            price_formatted = f"${item.unit_price:,.0f}".replace(",", ".")
            products_text += f"  - {item.product_name}{size_text} x{item.quantity} - {price_formatted}\n"
        
        shipping_text = ""
        if order.shipping_method:
            shipping_method_text = "Envío a domicilio" if order.shipping_method == "domicilio" else "Retiro en local"
            shipping_text = f"\nMétodo de envío: {shipping_method_text}"
            if order.shipping_address:
                shipping_text += f"\nDirección: {order.shipping_address}"
            if order.shipping_city:
                shipping_text += f"\nCiudad: {order.shipping_city}"
        
        text_content = f"""
Gracias por tu compra!

Hola {order.customer_name or 'Cliente'},

¡Gracias por elegirnos! Tu pago fue confirmado exitosamente y ya comenzamos a preparar tu pedido.

Número de pedido: {order.order_number}

Resumen de tu compra:
{products_text}
TOTAL: {total_formatted}
{shipping_text}

Ver estado de tu pedido: {tracking_url}

Tu pedido será confeccionado a medida. Te avisaremos por email cuando esté listo para ser enviado.

¿Tenés alguna pregunta? Respondé a este correo o contactanos por WhatsApp.

---
GEPE - Indumentaria Deportiva
        """
        
        # Enviar email
        params = {
            "from": os.getenv("RESEND_FROM_EMAIL", "GEPE <notificaciones@gepesport.com>"),
            "to": [order.customer_email],
            "subject": f"Confirmacion de compra - Pedido {order.order_number}",
            "html": html_content,
            "text": text_content,
        }

        reply_to = _get_default_reply_to()
        if reply_to:
            params["reply_to"] = [reply_to]
        
        response = resend.Emails.send(params)
        
        logger.info(f"Email de confirmación enviado a {order.customer_email}. Orden: {order.order_number}, ID: {response.get('id', 'N/A')}")
        return True
        
    except Exception as e:
        logger.error(f"Error al enviar email de confirmación: {str(e)}", exc_info=True)
        return False
