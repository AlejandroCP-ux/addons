# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FuelPlan(models.Model):
    _name = 'fuel.plan'
    _description = 'Propuesta de Plan de Combustible'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    
    name = fields.Char(string='Referencia', required=True, copy=False, default=lambda self: _('Nuevo'), tracking=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    
    # Campos relacionados con combustible no asignado
    unassigned_fuel_id = fields.Many2one('fuel.unassigned', string='Combustible No Asignado', required=True, tracking=True,
                                       domain=[('state', '=', 'confirmed')])
    carrier_id = fields.Many2one('fuel.carrier', string='Portador', related='unassigned_fuel_id.carrier_id', store=True, readonly=True)
    invoiced_fuel = fields.Float(string='Combustible Disponible', related='unassigned_fuel_id.amount', readonly=True, tracking=True)
    
    director_id = fields.Many2one('res.users', string='Director para Aprobación', tracking=True,
                                 domain=[('groups_id.category_id.name', '=', 'Gestión de Tarjetas de Combustible')])
    director_comments = fields.Text(string='Comentarios del Director', tracking=True)
    modified_by_director = fields.Boolean(string='Modificado por Director', default=False, tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending_approval', 'Pendiente de Aprobación'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)
    
    distribution_ids = fields.One2many('fuel.plan.distribution', 'plan_id', string='Distribución entre Tarjetas')
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('fuel.plan') or _('Nuevo')
        return super(FuelPlan, self).create(vals)
    
    @api.constrains('distribution_ids', 'invoiced_fuel')
    def _check_distribution_total(self):
        for plan in self:
            total_distributed = sum(plan.distribution_ids.mapped('amount'))
            if total_distributed > plan.invoiced_fuel:
                raise ValidationError(_("No puede distribuir más combustible del disponible."))
    
    @api.constrains('unassigned_fuel_id')
    def _check_unassigned_fuel_unique(self):
        """Verificar que no exista otro plan para el mismo combustible no asignado"""
        for plan in self:
            if plan.unassigned_fuel_id:
                existing_plan = self.search([
                    ('unassigned_fuel_id', '=', plan.unassigned_fuel_id.id),
                    ('id', '!=', plan.id),
                    ('state', '!=', 'cancelled')
                ])
                if existing_plan:
                    raise ValidationError(_("Ya existe un plan para este combustible no asignado: %s") % existing_plan.name)
    
    def action_generate_distribution(self):
        self.ensure_one()
        
        if not self.carrier_id:
            raise ValidationError(_("No se puede generar distribución sin un portador definido."))
        
        # Eliminar distribuciones existentes
        self.distribution_ids.unlink()
        
        # Obtener tarjetas activas del mismo portador
        cards = self.env['fuel.magnetic.card'].search([
            ('active', '=', True),
            ('state', 'in', ['available', 'assigned']),
            ('carrier_id', '=', self.carrier_id.id)
        ])
        
        if not cards:
            raise ValidationError(_("No hay tarjetas disponibles para el portador %s") % self.carrier_id.name)
        
        # Distribución equitativa entre tarjetas del mismo portador
        amount_per_card = self.invoiced_fuel / len(cards)
        distribution_vals = []
        
        for card in cards:
            distribution_vals.append({
                'plan_id': self.id,
                'card_id': card.id,
                'amount': amount_per_card,
            })
        
        self.env['fuel.plan.distribution'].create(distribution_vals)
        _logger.info("Distribución generada para plan %s con %d tarjetas", self.name, len(cards))
        
        return True
    
    def action_send_for_approval(self):
        self.ensure_one()
        
        if not self.distribution_ids:
            raise ValidationError(_("No puede enviar un plan sin distribución."))
        
        if not self.director_id:
            raise ValidationError(_("Debe seleccionar un director para la aprobación."))
        
        # Cambiar estado a pendiente de aprobación
        self.write({'state': 'pending_approval'})
        
        # Notificación en el chatter
        message = _("""
        <p><strong>Solicitud de Aprobación:</strong> Plan de Combustible {plan_name}</p>
        <p>Estimado/a {director},</p>
        <p>Se ha creado una nueva propuesta de plan de combustible que requiere su aprobación.</p>
        <p><strong>Referencia:</strong> {plan_name}<br/>
        <strong>Fecha:</strong> {date}<br/>
        <strong>Combustible Facturado:</strong> {fuel} litros</p>
        <a href="/web#model=fuel.plan&amp;id={id}&amp;view_type=form" class="btn btn-primary">Ver Propuesta</a>
        """).format(
            plan_name=self.name,
            director=self.director_id.name,
            date=self.date,
            fuel=self.invoiced_fuel,
            id=self.id
        )
        
        self.message_post(
            body=message,
            subject=_("Solicitud de Aprobación: Plan de Combustible %s") % self.name,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.director_id.partner_id.id]
        )
        
        return True
    
    def action_save_director_changes(self):
        self.ensure_one()
        
        current_user = self.env.user
        if current_user.id != self.director_id.id and not current_user.has_group('base.group_system'):
            raise ValidationError(_("Solo el director asignado puede modificar esta propuesta."))
        
        self.write({'modified_by_director': True})
        
        # Notificación en el chatter
        message = _("""
        <p>El director <strong>{director}</strong> ha realizado modificaciones en la propuesta de plan.</p>
        {comments}
        <a href="/web#model=fuel.plan&amp;id={id}&amp;view_type=form" class="btn btn-primary">Ver Plan Modificado</a>
        """).format(
            director=self.env.user.name,
            comments=_("<p><strong>Comentarios:</strong><br/>%s</p>") % self.director_comments if self.director_comments else "",
            id=self.id
        )
        
        self.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.create_uid.partner_id.id]
        )
        
        return True
    
    def action_approve(self):
        self.ensure_one()
        
        if not self.distribution_ids:
            raise ValidationError(_("No puede aprobar un plan sin distribución."))
        
        current_user = self.env.user
        if self.state == 'pending_approval' and current_user.id != self.director_id.id and not current_user.has_group('base.group_system'):
            raise ValidationError(_("Solo el director asignado puede aprobar esta propuesta."))
        
        self.write({'state': 'approved'})
        
        # Notificación en el chatter
        message = _("""
        <p>El plan ha sido <strong style="color: green;">APROBADO</strong> por {director}.</p>
        {modified}
        {comments}
        <a href="/web#model=fuel.plan&amp;id={id}&amp;view_type=form" class="btn btn-success">Ver Plan Aprobado</a>
        """).format(
            director=self.env.user.name,
            modified=_("<p>El plan fue modificado por el director antes de ser aprobado.</p>") if self.modified_by_director else "",
            comments=_("<p><strong>Comentarios:</strong><br/>%s</p>") % self.director_comments if self.director_comments else "",
            id=self.id
        )
        
        self.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.create_uid.partner_id.id]
        )
        
        return True
    
    def action_reject(self):
        self.ensure_one()
        
        current_user = self.env.user
        if self.state == 'pending_approval' and current_user.id != self.director_id.id and not current_user.has_group('base.group_system'):
            raise ValidationError(_("Solo el director asignado puede rechazar esta propuesta."))
        
        self.write({'state': 'rejected'})
        
        # Notificación en el chatter
        message = _("""
        <p>El plan ha sido <strong style="color: red;">RECHAZADO</strong> por {director}.</p>
        {comments}
        <a href="/web#model=fuel.plan&amp;id={id}&amp;view_type=form" class="btn btn-danger">Ver Plan Rechazado</a>
        """).format(
            director=self.env.user.name,
            comments=_("<p><strong>Motivo:</strong><br/>%s</p>") % self.director_comments if self.director_comments else "",
            id=self.id
        )
        
        self.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.create_uid.partner_id.id]
        )
        
        return True
    
    def action_reset_to_draft(self):
        self.ensure_one()
        
        if self.state in ['rejected', 'pending_approval']:
            self.write({'state': 'draft', 'modified_by_director': False})
            _logger.info("Plan %s regresado a borrador", self.name)
        
        return True
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
        _logger.info("Plan %s cancelado", self.name)
        return True
    
    @api.model
    def get_dashboard_data(self):
        try:
            pending_plans = self.search_count([('state', '=', 'pending_approval')])
            return {
                'pending_plans': pending_plans,
            }
        except Exception as e:
            _logger.error("Error al obtener datos del dashboard: %s", str(e))
            return {'pending_plans': 0}


class FuelPlanDistribution(models.Model):
    _name = 'fuel.plan.distribution'
    _description = 'Distribución del Plan de Combustible'
    
    plan_id = fields.Many2one('fuel.plan', string='Plan de Combustible', required=True, ondelete='cascade')
    card_id = fields.Many2one('fuel.magnetic.card', string='Tarjeta', required=True,
                            domain="[('carrier_id', '=', parent.carrier_id), ('active', '=', True), ('state', 'in', ['available', 'assigned'])]")
    amount = fields.Float(string='Importe', required=True)
    
    _sql_constraints = [
        ('card_plan_uniq', 'unique(plan_id, card_id)', 'Una tarjeta solo puede aparecer una vez en cada plan!')
    ]
