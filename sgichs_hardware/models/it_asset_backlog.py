# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class ITAssetBacklog(models.Model):
    _inherit = 'it.asset.backlog'

    def action_approve(self):
        """
        Extendemos la función de aprobación del core.
        Si el tipo es 'hardware', lo procesamos aquí.
        Si no, llamamos a la función original (super) para que otros
        módulos (como sgich_software) puedan procesar sus propios tipos.
        """
        # Primero, llamamos a la implementación original por si hay lógica genérica.
        # En nuestro caso, la implementación original lanza un error, así que
        # lo capturamos y continuamos.
        try:
            res = super(ITAssetBacklog, self).action_approve()
            # Si super() tuvo éxito (lo que no debería pasar con nuestra implementación base),
            # retornamos su resultado.
            return res
        except NotImplementedError:
            # Este es el comportamiento esperado del core, así que lo ignoramos y continuamos.
            pass

        self.ensure_one()
        if self.type == 'hardware':
            # Lógica para crear un activo de hardware
            HardwareAsset = self.env['it.asset.hardware']
            
            # Intentamos parsear los datos en bruto si existen
            raw_data = {}
            if self.raw_data:
                try:
                    raw_data = json.loads(self.raw_data)
                except json.JSONDecodeError:
                    pass # Ignorar si el JSON es inválido

            # Creamos el nuevo activo de hardware
            new_hardware = HardwareAsset.create({
                'name': self.name,
                'description': self.description,
                'subtype': raw_data.get('subtype', 'other'), # Valor por defecto
                'inventory_number': raw_data.get('inventory_number'),
                # Otros campos que puedan venir en raw_data
            })

            # Actualizamos el estado del registro del backlog
            self.write({'status': 'processed'})

            # Devolvemos una acción para abrir el nuevo activo creado
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'it.asset.hardware',
                'res_id': new_hardware.id,
                'view_mode': 'form',
                'target': 'current',
            }
        
        # Si no es de tipo hardware, lanzamos el error para indicar que falta un módulo.
        raise UserError(_("La lógica de aprobación para el tipo '%s' no está implementada. Instale el módulo correspondiente.") % self.type)