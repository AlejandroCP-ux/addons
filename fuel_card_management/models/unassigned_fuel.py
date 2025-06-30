# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError

class FuelUnassigned(models.Model):
    _name = 'fuel.unassigned'
    _description = 'Combustible No Asignado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    supplier_id = fields.Many2one('fuel.supplier', string='Proveedor', required=True, tracking=True)
    invoice_id = fields.Many2one('fuel.invoice', string='Factura', required=True, tracking=True)
    
    carrier_id = fields.Many2one('fuel.carrier', string='Portador de Combustible', required=True, tracking=True)
    
    amount = fields.Float(string='Cantidad (L)', required=True, tracking=True)
    unit_price = fields.Float(string='Precio Unitario', required=True, tracking=True)
    total_amount = fields.Float(string='Importe Total', compute='_compute_total_amount', store=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('used', 'Utilizado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    notes = fields.Text(string='Notas')
    
    # Campo para rastrear si fue creado desde una factura
    created_from_invoice = fields.Boolean(string='Creado desde Factura', default=False)
    
    # Campo para mostrar si ya tiene un plan asociado
    fuel_plan_id = fields.Many2one('fuel.plan', string='Plan de Combustible Asociado', readonly=True)
    has_fuel_plan = fields.Boolean(string='Tiene Plan Asociado', compute='_compute_has_fuel_plan', store=True)
    
    @api.model
    def create(self, vals):
        # Solo permitir creación si viene del contexto de una factura o es superusuario
        if not self.env.context.get('from_invoice_confirmation') and not self.env.user.has_group('base.group_system'):
            raise AccessError(_("No se puede crear combustible no asignado manualmente. "
                              "El combustible no asignado se genera automáticamente al confirmar una factura."))
        
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.unassigned') or _('Nuevo')
        
        # Marcar que fue creado desde factura
        if self.env.context.get('from_invoice_confirmation'):
            vals['created_from_invoice'] = True
            
        return super(FuelUnassigned, self).create(vals)
    
    @api.depends('amount', 'unit_price')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.amount * record.unit_price
    
    @api.depends('fuel_plan_id')
    def _compute_has_fuel_plan(self):
        for record in self:
            fuel_plan = self.env['fuel.plan'].search([
                ('unassigned_fuel_id', '=', record.id),
                ('state', '!=', 'cancelled')
            ], limit=1)
            record.fuel_plan_id = fuel_plan.id if fuel_plan else False
            record.has_fuel_plan = bool(fuel_plan)
    
    @api.constrains('carrier_id')
    def _check_carrier_id(self):
        for record in self:
            if not record.carrier_id:
                raise ValidationError(_("Debe seleccionar un portador de combustible."))
    
    def action_confirm(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'confirmed'
    
    def action_cancel(self):
        for record in self:
            if record.state != 'cancelled':
                # Verificar si tiene un plan asociado
                if record.has_fuel_plan and record.fuel_plan_id.state not in ['cancelled', 'rejected']:
                    raise ValidationError(_("No se puede cancelar combustible que tiene un plan activo asociado."))
                record.state = 'cancelled'
    
    def action_reset_to_draft(self):
        for record in self:
            if record.state == 'cancelled':
                record.state = 'draft'
    
    def action_create_fuel_plan(self):
        """Acción para crear un plan de combustible desde el combustible no asignado"""
        self.ensure_one()
        
        if self.state != 'confirmed':
            raise ValidationError(_("Solo se puede crear un plan desde combustible confirmado."))
        
        if self.has_fuel_plan:
            raise ValidationError(_("Ya existe un plan para este combustible no asignado."))
        
        # Crear nuevo plan de combustible
        plan_vals = {
            'unassigned_fuel_id': self.id,
            'date': fields.Date.today(),
            'director_id': False,  
        }
        
        new_plan = self.env['fuel.plan'].create(plan_vals)
        
        # Abrir el formulario del nuevo plan
        return {
            'type': 'ir.actions.act_window',
            'name': _('Plan de Combustible'),
            'res_model': 'fuel.plan',
            'res_id': new_plan.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def get_available_for_plans(self):
        """Método para obtener combustible disponible para crear planes"""
        return self.search([
            ('state', '=', 'confirmed'),
            ('has_fuel_plan', '=', False)
        ])
