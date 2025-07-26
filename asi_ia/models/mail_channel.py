from odoo import models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class Channel(models.Model):
    _inherit = 'mail.channel'

    def _notify_thread(self, message, msg_vals=None, **kwargs):
        if msg_vals is None:
            msg_vals = {}

        _logger.warning('***->ASI IA  entrando a notify_thread: %s', message)
        rdata = super(Channel, self)._notify_thread(message, msg_vals=msg_vals, **kwargs)
        _logger.warning('***->ASI IA  rdata: %s', rdata)

        # Referencias de configuración
        localai_channel_id = self.env.ref('asi_ia.channel_localai')
        user_localai = self.env.ref("asi_ia.user_localai")
        partner_localai = self.env.ref("asi_ia.partner_localai")

        author_id = msg_vals.get('author_id')
        prompt = msg_vals.get('body', '')
        if not prompt:
            _logger.warning('***->ASI IA  No hay prompt para procesar')
            return rdata

        partner_name = self.env['res.partner'].browse(author_id).name if author_id else ''

        try:
            # ✉️ Chats directos con IA
            if self.channel_type == 'chat':
                record_name = msg_vals.get('record_name', '')
                localai_name = f"{partner_localai.name or ''}, "

                if (author_id != partner_localai.id and
                        (localai_name in record_name or 'Local AI,' in record_name)):
                    _logger.warning('***->ASI IA  Condición de chat cumplida')
                    res = self.env['asi_ia.service'].get_ai_response(prompt)
                    _logger.warning('***->ASI IA  Respuesta obtenida: %s', res)
                    self.with_user(user_localai).message_post(
                        body=res,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment'
                    )

            # 💬 Mensajes en canal de la IA
            elif (msg_vals.get('model', '') == 'mail.channel' and
                  msg_vals.get('res_id', 0) == localai_channel_id.id and
                  author_id != partner_localai.id):
                _logger.warning('***->ASI IA  Condición de canal cumplida')
                res = self.env['asi_ia.service'].get_ai_response(prompt)
                _logger.warning('***->ASI IA  Respuesta obtenida: %s', res)
                localai_channel_id.with_user(user_localai).message_post(
                    body=res,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )

        except Exception as e:
            _logger.error('***->ASI IA  Error: %s', str(e))
            raise UserError(_("Error al procesar la respuesta de la IA: %s") % str(e))

        return rdata
