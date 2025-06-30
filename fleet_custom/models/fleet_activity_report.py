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

class FleetActivityReport(models.TransientModel):
    _name = 'fleet.activity.report'
    _description = 'Informe de Nivel de Actividad por Equipos'

    name = fields.Char(string='Nombre', default='Nivel de Actividad por Equipos')
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
            record.report_data = "Datos calculados para el informe"
    
    def action_generate_report(self):
        self.ensure_one()
        
        # Obtener datos para el informe
        data = self._get_report_data()
        
        # Generar PDF
        pdf_data = self._generate_pdf(data)
        
        # Guardar el PDF en el registro
        self.write({
            'pdf_file': base64.b64encode(pdf_data),
            'pdf_filename': f'Nivel_Actividad_Equipos_{self.year}_{self.month}.pdf'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.activity.report',
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
            'portadores': {}
        }
        
        # Obtener todos los vehículos con hojas de ruta en el período
        route_sheets = self.env['fleet.route.sheet'].search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed')
        ])
        
        # Agrupar por tipo de combustible (portador) y tipo de actividad
        for sheet in route_sheets:
            vehicle = sheet.vehicle_id
            fuel_type = vehicle.custom_fuel_type or vehicle.fuel_type or 'Desconocido'
            
            # Formatear el tipo de combustible
            if fuel_type == 'gasolina':
                fuel_type = 'Gasolina Motor (83 Octanos)'
            elif fuel_type == 'diesel':
                fuel_type = 'Combustible Diesel Regular'
            
            activity_type = vehicle.custom_activity_type_id.name if vehicle.custom_activity_type_id else 'Sin Actividad'
            
            # Inicializar el portador si no existe
            if fuel_type not in data['portadores']:
                data['portadores'][fuel_type] = {}
            
            # Inicializar la actividad si no existe
            if activity_type not in data['portadores'][fuel_type]:
                data['portadores'][fuel_type][activity_type] = {
                    'vehiculos': {},
                    'total_actividad': 0,
                    'unidad_medida': 'Km.' if not vehicle.is_technological else 'Horas'
                }
            
            # Inicializar el vehículo si no existe
            if vehicle.license_plate not in data['portadores'][fuel_type][activity_type]['vehiculos']:
                data['portadores'][fuel_type][activity_type]['vehiculos'][vehicle.license_plate] = 0
            
            # Sumar los kilómetros recorridos
            data['portadores'][fuel_type][activity_type]['vehiculos'][vehicle.license_plate] += sheet.total_kilometers
            data['portadores'][fuel_type][activity_type]['total_actividad'] += sheet.total_kilometers
        
        return data
    
    def _generate_pdf(self, data):
        """Generar PDF con los datos del informe"""
        buffer = io.BytesIO()
        
        # Crear el PDF
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Título
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width/2, height - 40, "Nivel de actividad por equipos")
        
        # Información de la empresa y período
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, f"TUN- {data['company']}")
        c.drawString(width - 150, height - 70, f"Año: {data['year']}")
        c.drawString(width - 150, height - 90, f"Mes: {data['month']}")
        
        # Encabezados de la tabla
        headers = ['Portador', 'Actividad', 'Matrícula', 'Nivel de Actividad', 'Unidad de medida']
        
        # Datos para la tabla
        table_data = [headers]
        
        y_position = height - 120
        
        # Para cada portador (tipo de combustible)
        for portador, actividades in data['portadores'].items():
            portador_row = [portador, '', '', '', '']
            table_data.append(portador_row)
            
            portador_total = 0
            
            # Para cada actividad
            for actividad, info in actividades.items():
                actividad_row = ['', actividad, '', '', '']
                table_data.append(actividad_row)
                
                # Para cada vehículo
                for matricula, nivel in info['vehiculos'].items():
                    vehiculo_row = ['', '', matricula, f"{nivel:.2f}", info['unidad_medida']]
                    table_data.append(vehiculo_row)
                
                # Subtotal de la actividad
                subtotal_row = ['', '', 'Subtotal:', f"{info['total_actividad']:.2f}", '']
                table_data.append(subtotal_row)
                
                # Total de la actividad
                total_act_row = ['', '', 'Total Actividad:', f"{info['total_actividad']:.2f}", '']
                table_data.append(total_act_row)
                
                portador_total += info['total_actividad']
            
            # Total del portador
            total_port_row = ['', '', 'Total portador:', f"{portador_total:.2f}", '']
            table_data.append(total_port_row)
        
        # Crear la tabla
        table = Table(table_data, colWidths=[100, 150, 100, 100, 100])
        
        # Estilo de la tabla
        style = TableStyle([
            ('BACKGROUND', (0, 0), (4, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (4, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (4, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (4, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (4, 0), 12),
            ('GRID', (0, 0), (4, -1), 1, colors.black),
        ])
        
        table.setStyle(style)
        
        # Dibujar la tabla
        table.wrapOn(c, width - 100, height)
        table.drawOn(c, 50, y_position - len(table_data) * 20)
        
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
