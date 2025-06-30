# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class FleetFicavRenewalWizard(models.TransientModel):
    _name = 'fleet.ficav.renewal.wizard'
    _description = 'Asistente para Renovación de FICAV'
    
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, readonly=True)
    current_expiry_date = fields.Date(string='Fecha de Vencimiento Actual', related='vehicle_id.ficav_expiry_date', readonly=True)
    new_expiry_date = fields.Date(string='Nueva Fecha de Vencimiento', required=True, default=lambda self: fields.Date.today() + relativedelta(years=1))
    notes = fields.Text(string='Notas')
    
    @api.constrains('new_expiry_date')
    def _check_new_expiry_date(self):
        for wizard in self:
            if wizard.new_expiry_date <= fields.Date.today():
                raise ValidationError(_("La nueva fecha de vencimiento debe ser futura."))
    
    def action_renew_ficav(self):
        self.ensure_one()
        
        # Actualizar la fecha de vencimiento del FICAV
        self.vehicle_id.write({
            'ficav_expiry_date': self.new_expiry_date
        })
        
        # Crear una nota en el chatter del vehículo
        self.vehicle_id.message_post(
            body=_("FICAV renovado. Nueva fecha de vencimiento: %s. Notas: %s") % 
                 (self.new_expiry_date, self.notes or 'Ninguna'),
            subject=_("Renovación de FICAV")
        )
        
        return {'type': 'ir.actions.act_window_close'}
