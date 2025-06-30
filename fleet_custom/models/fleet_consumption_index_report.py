# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

class FleetConsumptionIndexReport(models.TransientModel):
    _name = 'fleet.consumption.index.report'
    _description = 'Informe de Índice de Consumo'

    name = fields.Char(string='Nombre', default='Índice de Consumo')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    date_from = fields.Date(string='Fecha Desde', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Fecha Hasta', required=True, default=lambda self: fields.Date.today())
    year = fields.Integer(string='Año', compute='_compute_year_month', store=True)
    month = fields.Integer(string='Mes', compute='_compute_year_month', store=True)
    report_data = fields.Text(string='Datos del Informe', compute='_compute_report_data')
    pdf_file = fields.Binary(string='Archivo PDF')
    pdf_filename = fields.Char(string='Nombre del archivo PDF')
    
    @api.depends('date_from', 'date_to')
    def _compute_year_month(self):
        for record in self:
            if record.date_from:
                record.year = record.date_from.year
                record.month = record.date_from.month
    
    @api.depends('date_from', 'date_to')
    def _compute_report_data(self):
        for record in self:
            # Aquí se calcularían los datos del informe
            record.report_data = "Datos calculados para el informe de índice de consumo"
    
    def action_generate_report(self):
        self.ensure_one()
        
        # Obtener datos para el informe
        data = self._get_report_data()
        
        # Generar PDF
        pdf_data = self._generate_pdf(data)
        
        # Guardar el PDF en el registro
        self.write({
            'pdf_file': base64.b64encode(pdf_data),
            'pdf_filename': f'Indice_Consumo_{self.year}_{self.month}.pdf'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.consumption.index.report',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }
    
    def _get_report_data(self):
        """Obtener datos para el informe"""
        self.ensure_one()
        
        # Estructura para almacenar los datos del informe
        data = {
            'company': self.company_id.name,
            'year': self.year,
            'month': self.month,
            'vehiculos': []
        }
        
        # Obtener todos los vehículos con registros de combustible en el período
        fuel_records = self.env['fleet.fuel.record'].search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed')
        ])
        
        # Obtener datos de consumo para cada vehículo
        for record in fuel_records:
            vehicle = record.vehicle_id
            
            # Buscar el índice de consumo planificado
            consumption_index = self.env['fleet.consumption.index'].search([
                ('vehicle_id', '=', vehicle.id)
            ], limit=1)
            
            # Calcular desviación
            desviacion = 0
            if consumption_index and consumption_index.current_consumption_index > 0 and record.real_consumption_index > 0:
                desviacion = ((record.real_consumption_index / consumption_index.current_consumption_index) - 1) * 100
        
        # Determinar si la desviación es significativa (más del 5%)
        desv_significativa = '*' if abs(desviacion) > 5 else ''
        
        # Calcular consumo aproximado de combustible
        consumo_aproximado = 0
        if consumption_index and consumption_index.current_consumption_index > 0:
            consumo_aproximado = record.total_kilometers / consumption_index.current_consumption_index
        
        # Añadir datos del vehículo
        data['vehiculos'].append({
            'matricula': vehicle.license_plate,
            'nivel_actividad': record.total_kilometers,
            'unidad_medida': 'Km.' if not vehicle.is_technological else 'Horas',
            'litros_tanque_anterior': record.previous_odometer,
            'consumo_litros': record.total_fuel_consumed,
            'comb_terceros': 0,  # Este dato no está disponible en el sistema actual
            'litros_tanque_actual': record.closing_fuel,
            'consumo_real': record.total_fuel_consumed,
            'consumo_aproximado': consumo_aproximado,  # Nuevo campo
            'indice_consumo': record.real_consumption_index,
            'indice_plan': consumption_index.current_consumption_index if consumption_index else 0,
            'desviacion': desviacion,
            'desv_significativa': desv_significativa
        })
    
        return data
    
    def _generate_pdf(self, data):
        """Generar PDF con los datos del informe"""
        buffer = io.BytesIO()
        
        # Crear el PDF
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Título
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 40, "Índice de consumo")
        
        # Información de la empresa y período
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, f"TUN- {data['company']}")
        c.drawString(width - 150, height - 70, f"Año: {data['year']}")
        c.drawString(width - 150, height - 90, f"Mes: {data['month']}")
        
        # Encabezados de la tabla
        headers = [
            'Matrícula', 'Nivel Actividad', 'Unidad de medida', 'Litros en tanque mes anterior',
            'Consumo litros', 'Comb. de Terceros litros', 'Litros en tanque mes actual',
            'Consumo Real', 'Consumo Aprox.', 'Índice Consumo', 'Índice Plan', '% Desv.', 'Desv. > 5 %'
        ]
        
        # Datos para la tabla
        table_data = [headers]
        
        # Añadir datos de vehículos
        for vehiculo in data['vehiculos']:
            row = [
                vehiculo['matricula'],
                f"{vehiculo['nivel_actividad']:.2f}",
                vehiculo['unidad_medida'],
                f"{vehiculo['litros_tanque_anterior']:.2f}",
                f"{vehiculo['consumo_litros']:.2f}",
                f"{vehiculo['comb_terceros']:.2f}",
                f"{vehiculo['litros_tanque_actual']:.2f}",
                f"{vehiculo['consumo_real']:.2f}",
                f"{vehiculo['consumo_aproximado']:.2f}",  # Nuevo campo
                f"{vehiculo['indice_consumo']:.2f}",
                f"{vehiculo['indice_plan']:.2f}",
                f"{vehiculo['desviacion']:.2f}",
                vehiculo['desv_significativa']
            ]
            table_data.append(row)
        
        # Crear la tabla
        table = Table(table_data, colWidths=[55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 55, 40])
        
        # Estilo de la tabla
        style = TableStyle([
            ('BACKGROUND', (0, 0), (12, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (12, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (12, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (12, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (12, 0), 12),
            ('GRID', (0, 0), (12, -1), 1, colors.black),
            ('ALIGN', (1, 1), (12, -1), 'RIGHT'),
        ])
        
        table.setStyle(style)
        
        # Dibujar la tabla
        table.wrapOn(c, width - 80, height)
        table.drawOn(c, 40, height - 120 - len(table_data) * 20)
        
        c.save()
        
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
    
    def action_print_report(self):
        """Imprimir el informe"""
        self.ensure_one()
        
        if not self.pdf_file:
            self.action_generate_report()
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true',
            'target': 'self',
        }
