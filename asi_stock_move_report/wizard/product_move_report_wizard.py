# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import datetime, timedelta, date
import calendar
from odoo.exceptions import UserError

class ProductMoveReportWizard(models.TransientModel):
    _name = 'product.move.report.wizard'
    _description = 'Asistente para Reporte de Movimientos por Producto'

    # Campo para seleccionar el producto
    product_id = fields.Many2one('product.product', string='Producto', required=True, 
                                domain=[('type', '=', 'product')])

    period_type = fields.Selection([
        ('week', 'Semana'),
        ('month', 'Mes'),
        ('year', 'Año'),
        ('custom', 'Personalizado'),
    ], string='Tipo de Período', default='month', required=True)
    
    # Campos para selección de semana
    week_month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes', default=lambda self: str(fields.Date.today().month))
    
    week_year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    
    week_number = fields.Selection([
        ('1', '1ra Semana'),
        ('2', '2da Semana'),
        ('3', '3ra Semana'),
        ('4', '4ta Semana'),
        ('5', '5ta Semana')
    ], string='Semana', default='1')
    
    # Campos para selección de mes
    month = fields.Selection([
        ('1', 'Enero'), ('2', 'Febrero'), ('3', 'Marzo'), ('4', 'Abril'),
        ('5', 'Mayo'), ('6', 'Junio'), ('7', 'Julio'), ('8', 'Agosto'),
        ('9', 'Septiembre'), ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes', default=lambda self: str(fields.Date.today().month))
    
    month_year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    
    # Campo para selección de año
    year = fields.Integer(string='Año', default=lambda self: fields.Date.today().year)
    
    # Campos para selección personalizada
    custom_date_from = fields.Date(string='Fecha de Inicio', default=fields.Date.today)
    custom_date_to = fields.Date(string='Fecha de Fin', default=fields.Date.today)
    
    # Campos ocultos para almacenar las fechas de inicio y fin calculadas
    date_start = fields.Datetime(string='Fecha Inicio', required=True)
    date_end = fields.Datetime(string='Fecha Fin', required=True)
    
    @api.constrains('custom_date_from', 'custom_date_to')
    def _check_custom_dates(self):
        for record in self:
            if record.period_type == 'custom' and record.custom_date_from and record.custom_date_to:
                if record.custom_date_from > record.custom_date_to:
                    raise UserError('La fecha de inicio no puede ser mayor que la fecha de fin.')
    
    @api.onchange('period_type', 'week_month', 'week_year', 'week_number', 'month', 'month_year', 'year', 'custom_date_from', 'custom_date_to')
    def _onchange_period_fields(self):
        """Actualiza las fechas de inicio y fin basadas en los campos seleccionados"""
        if self.period_type == 'week' and self.week_month and self.week_year and self.week_number:
            # Para semana: calculamos el primer día del mes
            month = int(self.week_month)
            year = self.week_year
            week_num = int(self.week_number)
            
            # Primer día del mes
            first_day = date(year, month, 1)
            
            # Calculamos el inicio de la semana seleccionada
            start_day = 1 + (week_num - 1) * 7
            
            # Verificamos que el día exista en el mes
            last_day_of_month = calendar.monthrange(year, month)[1]
            if start_day > last_day_of_month:
                start_day = last_day_of_month
            
            start_date = datetime.combine(date(year, month, start_day), datetime.min.time())
            
            # La semana termina 6 días después o el último día del mes
            end_day = min(start_day + 6, last_day_of_month)
            end_date = datetime.combine(date(year, month, end_day), datetime.max.time())
            
        elif self.period_type == 'month' and self.month and self.month_year:
            # Para mes: desde el primer día hasta el último día del mes seleccionado
            month = int(self.month)
            year = self.month_year
            
            start_date = datetime.combine(date(year, month, 1), datetime.min.time())
            
            # Último día del mes
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime.combine(date(year, month, last_day), datetime.max.time())
            
        elif self.period_type == 'year' and self.year:
            # Para año: desde el 1 de enero hasta el 31 de diciembre
            year = self.year
            
            start_date = datetime.combine(date(year, 1, 1), datetime.min.time())
            end_date = datetime.combine(date(year, 12, 31), datetime.max.time())
            
        elif self.period_type == 'custom' and self.custom_date_from and self.custom_date_to:
            # Para período personalizado: usar las fechas seleccionadas
            start_date = datetime.combine(self.custom_date_from, datetime.min.time())
            end_date = datetime.combine(self.custom_date_to, datetime.max.time())
            
        else:
            # Si no se han completado los campos necesarios, no actualizamos las fechas
            return
        
        self.date_start = start_date
        self.date_end = end_date
    
    def action_generate_report(self):
        """
        Genera el reporte PDF de movimientos por producto
        """
        self.ensure_one()
        
        # Aseguramos que las fechas estén actualizadas
        self._onchange_period_fields()
        
        # Validar que hay movimientos en el rango de fechas para el producto
        moves_count = self.env['stock.move'].search_count([
            ('date', '>=', self.date_start),
            ('date', '<=', self.date_end),
            ('state', '=', 'done'),
            ('product_id', '=', self.product_id.id),
        ])
        
        if moves_count == 0:
            raise UserError(f'No se encontraron movimientos para el producto {self.product_id.name} en el período seleccionado.')
        
        # Preparar datos para el reporte
        data = {
            'date_start': self.date_start+timedelta(days=1),
            'date_end': self.date_end,
            'product_id': self.product_id.id,
        }
        
        # Generar el reporte PDF
        return self.env.ref('asi_stock_move_report.action_report_product_move').report_action(
            self, data=data
        )
