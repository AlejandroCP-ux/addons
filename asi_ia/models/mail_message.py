from odoo import api, models

class ChatGPTMessage(models.Model):
    _inherit = 'mail.message'

    def convert_data(self, message):
        """
        Convierte los datos del mensaje asegurando que todos los campos necesarios estén presentes.
        Este método es especialmente importante para la integración con ChatGPT.
        """
        # Validación inicial del mensaje
        if not message:
            raise ValidationError("El mensaje no puede estar vacío")

        # Crear estructura base si attachment_ids no existe
        if not hasattr(message, 'attachment_ids'):
            message.attachment_ids = []

        # Estructura completa del mensaje
        result = {
            'attachment_ids': message.attachment_ids,
            'author_id': message.author_id.id if hasattr(message, 'author_id') else False,
            'body': message.body if hasattr(message, 'body') else '',
            'channel_ids': message.channel_ids.ids if hasattr(message, 'channel_ids') else [],
            'date': message.date if hasattr(message, 'date') else fields.Datetime.now(),
            'email_from': message.email_from if hasattr(message, 'email_from') else False,
            'message_id': message.message_id if hasattr(message, 'message_id') else False,
            'message_type': message.message_type if hasattr(message, 'message_type') else 'notification',
            'model': message.model if hasattr(message, 'model') else False,
            'partner_ids': [p.id for p in message.partner_ids] if hasattr(message, 'partner_ids') else [],
            'record_name': message.record_name if hasattr(message, 'record_name') else False,
            'res_id': message.res_id if hasattr(message, 'res_id') else False,
            'subtype_id': message.subtype_id.id if hasattr(message, 'subtype_id') else False,
            'subject': message.subject if hasattr(message, 'subject') else '',
        }

        # Llamada al método original para procesamiento adicional
        return super().convert_data(message) 
        
    def prepare_message_values(self, values):
        result = super().prepare_message_values(values)
        
        # Asegurar que attachment_ids existe
        if 'attachment_ids' not in result:
            result['attachment_ids'] = []
            
        return result