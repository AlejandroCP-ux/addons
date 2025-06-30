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

class FleetConsumptionAnalysisReport(models.TransientModel):
    _name = 'fleet.consumption.analysis.report'
    _description = 'Informe de Consumo de Combustible y Análisis de Indicadores'

    name = fields.Char(string='Nombre', default='Consumo de Combustible y Análisis de Indicadores')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    date_from = fields.Date(string='Fecha Desde', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Fecha Hasta', required=True, default=lambda self: fields.Date.today())
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True)
    report_data = fields.Text(string='Datos del Informe', compute='_compute_report_data')
    pdf_file = fields.Binary(string='Archivo PDF')
    pdf_filename = fields.Char(string='Nombre del archivo PDF')
    
    @api.depends('date_from', 'date_to', 'vehicle_id')
    def _compute_report_data(self):
        for record in self:
            # Aquí se calcularían los datos del informe
            record.report_data = "Datos calculados para el informe de análisis de consumo"
    
    def action_generate_report(self):
        self.ensure_one()
        
        # Obtener datos para el informe
        data = self._get_report_data()
        
        # Generar PDF
        pdf_data = self._generate_pdf(data)
        
        # Guardar el PDF en el registro
        self.write({
            'pdf_file': base64.b64encode(pdf_data),
            'pdf_filename': f'Analisis_Consumo_{self.vehicle_id.license_plate}_{self.date_from.strftime("%m%Y")}-{self.date_to.strftime("%m%Y")}.pdf'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.consumption.analysis.report',
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
            'date_from': self.date_from,
            'date_to': self.date_to,
            'vehicle': {
                'id': self.vehicle_id.id,
                'name': self.vehicle_id.name,
                'matricula': self.vehicle_id.license_plate,
                'descripcion': f"{self.vehicle_id.model_id.brand_id.name} {self.vehicle_id.model_id.name}",
                'actividad': self.vehicle_id.custom_activity_type_id.name if self.vehicle_id.custom_activity_type_id else 'Sin Actividad',
                'combustible': self.vehicle_id.custom_fuel_type or self.vehicle_id.fuel_type or 'Desconocido'
            },
            'registros': []
        }
        
        # Formatear el tipo de combustible
        if data['vehicle']['combustible'] == 'gasolina':
            data['vehicle']['combustible'] = 'Gasolina Motor (83 Octanos)'
        elif data['vehicle']['combustible'] == 'diesel':
            data['vehicle']['combustible'] = 'Combustible Diesel Regular'
        
        # Obtener registros de combustible para el vehículo en el período
        fuel_records = self.env['fleet.fuel.record'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed')
        ])
        
        # Buscar el índice de consumo planificado
        consumption_index = self.env['fleet.consumption.index'].search([
            ('vehicle_id', '=', self.vehicle_id.id)
        ], limit=1)
        
        # Procesar registros
        total_nivel_actividad = 0
        total_consumo_real = 0
        total_combustible_debido = 0
        
        for record in fuel_records:
            # Calcular combustible que debió consumir
            combustible_debido = 0
            if consumption_index and consumption_index.current_consumption_index > 0:
                combustible_debido = record.total_kilometers / consumption_index.current_consumption_index
            
            # Calcular diferencias
            diferencia = record.total_fuel_consumed - combustible_debido
            
            # Calcular desviación
            desviacion = 0
            if combustible_debido > 0:
                desviacion = (diferencia / combustible_debido) * 100
            
            # Añadir registro
            data['registros'].append({
                'nivel_actividad': record.total_kilometers,
                'consumo_real': record.total_fuel_consumed,
                'combustible_debido': combustible_debido,
                'indice_real': record.real_consumption_index,
                'indice_normado': consumption_index.current_consumption_index if consumption_index else 0,
                'diferencia': diferencia,
                'desviacion': desviacion,
                'desviacion_abs': abs(diferencia)
            })
            
            # Actualizar totales
            total_nivel_actividad += record.total_kilometers
            total_consumo_real += record.total_fuel_consumed
            total_combustible_debido += combustible_debido
        
        # Añadir totales
        data['totales'] = {
            'nivel_actividad': total_nivel_actividad,
            'consumo_real': total_consumo_real,
            'combustible_debido': total_combustible_debido,
            'indice_real': total_consumo_real / total_nivel_actividad if total_nivel_actividad > 0 else 0,
            'diferencia': total_consumo_real - total_combustible_debido,
            'desviacion': ((total_consumo_real / total_combustible_debido) - 1) * 100 if total_combustible_debido > 0 else 0,
            'desviacion_abs': abs(total_consumo_real - total_combustible_debido)
        }
        
        return data
    
    def _generate_pdf(self, data):
        """Generar PDF con los datos del informe"""
        buffer = io.BytesIO()
        
        # Crear el PDF
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Título
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, height - 40, "Consumo de combustible y análisis de los")
        c.drawCentredString(width/2, height - 60, "indicadores de desempeño energético por equipo")
        
        # Información del período
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 90, f"Desde: {data['date_from'].strftime('%m/%Y')}")
        c.drawString(width - 150, height - 90, f"Hasta: {data['date_to'].strftime('%m/%Y')}")
        
        # Información de la empresa y vehículo
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 120, "Empresa:")
        c.drawString(50, height - 140, "Actividad:")
        c.drawString(50, height - 160, "Producto:")
        
        c.setFont("Helvetica", 10)
        c.drawString(150, height - 120, f"TUN- {data['company']}")
        c.drawString(150, height - 140, f"{data['vehicle']['actividad']}")
        c.drawString(150, height - 160, f"{data['vehicle']['combustible']}")
        
        # Encabezados de la tabla
        headers = [
            'No.', 'Descripción y tipo vehículo', 'Matrícula', 'Índice de Consumo por datos de fábrica (UM)/lts',
            'Nivel de Actividad Real (UM)', 'Consumo Real (lts)', 'Combustible que debió Consumir (Lts)',
            'Índice consumo real (UM)/lts', 'Índice Cons.Normado. (UM)/lts', 'Diferencias en Consumo (litros).',
            '% Desviación del índice normado.', 'Desv. Abs.'
        ]
        
        # Datos para la tabla
        table_data = [headers]
        
        # Añadir datos del vehículo
        row = [
            '(1)',
            f"(2)\n{data['vehicle']['descripcion']}",
            f"(3)\n{data['vehicle']['matricula']}",
            f"(4)\n{data['registros'][0]['indice_normado']:.2f}" if data['registros'] else '(4)',
            f"(5)\n{data['totales']['nivel_actividad']:.2f}",
            f"(6)\n{data['totales']['consumo_real']:.2f}",
            f"(7)\n{data['totales']['combustible_debido']:.2f}",
            f"(8)\n{data['totales']['indice_real']:.2f}",
            f"(9)\n{data['registros'][0]['indice_normado']:.2f}" if data['registros'] else '(9)',
            f"(10)\n{data['totales']['diferencia']:.2f}",
            f"(11)\n{data['totales']['desviacion']:.2f}",
            f"{data['totales']['desviacion_abs']:.2f}"
        ]
        table_data.append(row)
        
        # Añadir fila de totales
        total_row = [
            'Total',
            '',
            '',
            '',
            f"{data['totales']['nivel_actividad']:.2f}",
            f"{data['totales']['consumo_real']:.2f}",
            f"{data['totales']['combustible_debido']:.2f}",
            f"{data['totales']['indice_real']:.2f}",
            '',
            f"{data['totales']['diferencia']:.2f}",
            f"{data['totales']['desviacion']:.2f}",
            f"{data['totales']['desviacion_abs']:.2f}"
        ]
        table_data.append(total_row)
        
        # Crear la tabla
        table = Table(table_data, colWidths=[30, 80, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50])
        
        # Estilo de la tabla
        style = TableStyle([
            ('BACKGROUND', (0, 0), (11, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (11, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (11, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (11, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (11, 0), 12),
            ('GRID', (0, 0), (11, -1), 1, colors.black),
            ('ALIGN', (4, 1), (11, -1), 'RIGHT'),
            ('BACKGROUND', (0, -1), (11, -1), colors.lightgrey),
        ])
        
        table.setStyle(style)
        
        # Dibujar la tabla
        table.wrapOn(c, width - 60, height)
        table.drawOn(c, 30, height - 200 - len(table_data) * 30)
        
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
