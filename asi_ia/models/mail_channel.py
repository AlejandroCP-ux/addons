# -*- coding: utf-8 -*-
# Copyright (c) 2020-Present InTechual Solutions. (<https://intechualsolutions.com/>)

from openai import OpenAI

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class Channel(models.Model):
    _inherit = 'mail.channel'

    def _notify_thread(self, message, msg_vals=None, **kwargs):
        if msg_vals is None:
            msg_vals = {} 
        
        _logger.warning('***->LLMStudio  entrando a notify_thread: %s', message)
        rdata = super(Channel, self)._notify_thread(message, msg_vals=msg_vals, **kwargs)
        _logger.warning('***->LLMStudio  rdata: %s', rdata)
        
        localai_channel_id = self.env.ref('asi_ia.channel_localai')
        user_localai = self.env.ref("asi_ia.user_localai")
        partner_localai = self.env.ref("asi_ia.partner_localai")
        
        _logger.warning('***->LLMStudio  msg_vals: %s', msg_vals)
        
        author_id = msg_vals.get('author_id')
        prompt = msg_vals.get('body', '')       
        if not prompt:
            _logger.warning('***->LLMStudio  No hay prompt para procesar')
            return rdata
            
        Partner = self.env['res.partner']
        partner_name = Partner.browse(author_id).name if author_id else ''
    
        try:
            # Para chats directos
            if self.channel_type == 'chat':
                _logger.warning('***->LLMStudio  Es un chat directo')
                record_name = msg_vals.get('record_name', '')
                localai_name = f"{partner_localai.name or ''}, "
                
                if (author_id != partner_localai.id and 
                    (localai_name in record_name or 'Local AI,' in record_name)):
                    _logger.warning('***->LLMStudio  Condición de chat cumplida')
                    res = self._get_localai_response(prompt=prompt)
                    _logger.warning('***->LLMStudio  Respuesta obtenida: %s', res)
                    self.with_user(user_localai).message_post(
                        body=res, 
                        message_type='comment', 
                        subtype_xmlid='mail.mt_comment'
                    )
                                # Notificar al bus para actualización en tiempo real
                    # self._broadcast([self.env.user.partner_id.id])
                                                        
                    # self.env['bus.bus']._sendone(
                    # self.env.user.partner_id,
                    # 'mail.message/insert',
                    # {'message': {'id': message.id}}
                    # )
                

                    
            # Para mensajes en el canal de local ai
            elif (msg_vals.get('model', '') == 'mail.channel' and 
                  msg_vals.get('res_id', 0) == localai_channel_id.id and 
                  author_id != partner_localai.id):
                _logger.warning('***->LLMStudio  Condición de canal cumplida')
                res = self._get_localai_response(prompt=prompt)
                _logger.warning('***->LLMStudio  Respuesta obtenida: %s', res)
                localai_channel_id.with_user(user_localai).message_post(
                    body=res, 
                    message_type='comment', 
                    subtype_xmlid='mail.mt_comment'
                )
                
        except Exception as e:
            _logger.error('***->LLMStudio  Error: %s', str(e))
            raise UserError(_("Error al procesar la respuesta de la IA Local: %s") % str(e))
    
        return rdata
        
    def _get_localai_response(self, prompt):
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('asi_ia.openapi_api_key')
        url= ICP.get_param('asi_ia.openapi_base_url')
        _logger.warning('***->url del endpoint: %s' % url)      
        client = OpenAI(base_url=url, api_key="noapykey")
        localai_model_id = ICP.get_param('asi_ia.localai_model_id')
        _logger.warning('***->tomando parametro localai_model_id : %s' % localai_model_id)  
        try:
            if localai_model_id:
                localai_model = self.env['localai.model'].browse(int(localai_model_id)).name
                _logger.warning('***->va a usar el modelo: %s' % localai_model)      
        except Exception as ex:
            localai_model = 'qwen2-0.5b-instruct'
            pass
        try:
            _logger.warning('***->LLMStudio  propmt data: %s' % prompt)        
            response = client.chat.completions.create(
                messages=[{"role": "system", "content": prompt}],
                model=localai_model,
                temperature=0.6,
                max_tokens=3000,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                user=self.env.user.name
            )
            res = response.choices[0].message.content
            _logger.warning('***->LLMStudio  output data: %s' % res)            
            return res
        except Exception as e:
            raise UserError(_(e))
