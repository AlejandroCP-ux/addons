# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from dateutil.relativedelta import relativedelta
import io
import base64
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class FleetPlanVsRealReportLine(models.TransientModel):
    _name = 'fleet.plan.vs.real.report.line'
    _description = 'Línea de Informe Plan vs Real'
    
    report_id = fields.Many2one('fleet.plan.vs.real.report', string='Informe', ondelete='cascade')
    vehicle_name = fields.Char(string='Vehículo')
    license_plate = fields.Char(string='Matrícula')
    vehicle_type = fields.Char(string='Tipo')
    planned_fuel = fields.Float(string='Plan (Litros)')
    real_fuel = fields.Float(string='Real (Litros)')
    difference = fields.Float(string='Diferencia (Litros)')
    compliance_percentage = fields.Float(string='% Cumplimiento')
    status = fields.Char(string='Estado')

class FleetPlanVsRealReport(models.TransientModel):
    _name = 'fleet.plan.vs.real.report'
    _description = 'Informe Plan vs Real'

    name = fields.Char(string='Nombre', default='Plan vs Real')
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    date_from = fields.Date(string='Fecha Desde', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Fecha Hasta', required=True, default=lambda self: fields.Date.today())
    year = fields.Integer(string='Año', compute='_compute_year_month', store=True)
    month = fields.Integer(string='Mes', compute='_compute_year_month', store=True)
    vehicle_type = fields.Selection([
        ('all', 'Todos'),
        ('normal', 'Vehículos Normales'),
        ('technological', 'Vehículos Tecnológicos'),
        ('administrative', 'Vehículos Administrativos')
    ], string='Tipo de Vehículo', default='all', required=True)
    report_data = fields.Text(string='Datos del Informe', compute='_compute_report_data')
    pdf_file = fields.Binary(string='Archivo PDF')
    pdf_filename = fields.Char(string='Nombre del archivo PDF')
    plan_vs_real_line_ids = fields.One2many('fleet.plan.vs.real.report.line', 'report_id', string='Líneas del Informe')
    
    @api.depends('date_from', 'date_to')
    def _compute_year_month(self):
        for record in self:
            if record.date_from:
                record.year = record.date_from.year
                record.month = record.date_from.month
    
    @api.depends('date_from', 'date_to', 'vehicle_type')
    def _compute_report_data(self):
        for record in self:
            record.report_data = "Datos calculados para el informe Plan vs Real"
    
    def action_generate_report(self):
        self.ensure_one()
        
        # Obtener datos para el informe
        data = self._get_report_data()
        
        # Generar PDF
        pdf_data = self._generate_pdf(data)
        
        # Guardar el PDF en el registro
        self.write({
            'pdf_file': base64.b64encode(pdf_data),
            'pdf_filename': f'Plan_vs_Real_{self.year}_{self.month}_{self.vehicle_type}.pdf'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.plan.vs.real.report',
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
            'vehicle_type': dict(self._fields['vehicle_type'].selection).get(self.vehicle_type),
            'comparaciones': [],
            'totales': {
                'plan_total': 0,
                'real_total': 0,
                'diferencia_total': 0,
                'porcentaje_cumplimiento': 0
            }
        }
        
        # Buscar planes de consumo para el período
        plans = self.env['fleet.consumption.plan'].search([
            ('year', '=', self.year),
            ('month', '=', str(self.month)),
            ('state', '=', 'confirmed')
        ])
        
        for plan in plans:
            # Procesar asignaciones por vehículos
            for vehicle_allocation in plan.vehicle_allocation_ids:
                vehicle = vehicle_allocation.vehicle_id
                
                # Filtrar por tipo de vehículo si es necesario
                if self.vehicle_type != 'all':
                    if self.vehicle_type == 'normal' and vehicle.is_technological:
                        continue
                    elif self.vehicle_type == 'technological' and not vehicle.is_technological:
                        continue
                    elif self.vehicle_type == 'administrative' and vehicle.has_route_sheet:
                        continue
                
                # Obtener consumo real del vehículo
                real_consumption = self._get_real_consumption(vehicle)
                
                # Calcular diferencia y porcentaje
                diferencia = real_consumption - vehicle_allocation.allocated_fuel
                porcentaje = (real_consumption / vehicle_allocation.allocated_fuel * 100) if vehicle_allocation.allocated_fuel > 0 else 0
                
                data['comparaciones'].append({
                    'vehiculo': vehicle.name,
                    'matricula': vehicle.license_plate,
                    'tipo': 'Tecnológico' if vehicle.is_technological else 'Normal',
                    'plan_combustible': vehicle_allocation.allocated_fuel,
                    'real_combustible': real_consumption,
                    'diferencia': diferencia,
                    'porcentaje_cumplimiento': porcentaje,
                    'estado': 'Exceso' if diferencia > 0 else 'Ahorro' if diferencia < 0 else 'Exacto'
                })
                
                # Actualizar totales
                data['totales']['plan_total'] += vehicle_allocation.allocated_fuel
                data['totales']['real_total'] += real_consumption
        
        # Calcular totales finales
        data['totales']['diferencia_total'] = data['totales']['real_total'] - data['totales']['plan_total']
        data['totales']['porcentaje_cumplimiento'] = (
            data['totales']['real_total'] / data['totales']['plan_total'] * 100
        ) if data['totales']['plan_total'] > 0 else 0
        
        return data
    
    def _get_real_consumption(self, vehicle):
        """Obtener el consumo real de un vehículo en el período"""
        # Para vehículos administrativos, buscar en registros de combustible
        if not vehicle.has_route_sheet:
            fuel_records = self.env['fleet.fuel.record'].search([
                ('vehicle_id', '=', vehicle.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('state', '=', 'confirmed')
            ])
            return sum(record.total_fuel_consumed for record in fuel_records)
        
        # Para vehículos con hojas de ruta, calcular basado en kilómetros y consumo
        route_sheets = self.env['fleet.route.sheet'].search([
            ('vehicle_id', '=', vehicle.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'confirmed')
        ])
        
        total_kilometers = sum(sheet.total_kilometers for sheet in route_sheets)
        
        # Buscar índice de consumo del vehículo
        consumption_index = self.env['fleet.consumption.index'].search([
            ('vehicle_id', '=', vehicle.id)
        ], limit=1)
        
        if consumption_index and consumption_index.current_consumption_index > 0:
            return total_kilometers / consumption_index.current_consumption_index
        
        return 0
    
    def _generate_pdf(self, data):
        """Generar PDF con los datos del informe"""
        buffer = io.BytesIO()
        
        # Crear el PDF
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.darkblue
        )
        
        # Título
        c.setFont("Helvetica-Bold", 18)
        c.setFillColor(colors.darkblue)
        c.drawCentredString(width/2, height - 50, "INFORME PLAN VS REAL")
        c.drawCentredString(width/2, height - 75, "Comparación de Consumo de Combustible")
        
        # Información del período
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.black)
        c.drawString(50, height - 110, f"Empresa: TUN- {data['company']}")
        c.drawString(50, height - 130, f"Período: {data['month']}/{data['year']}")
        c.drawString(50, height - 150, f"Tipo de Vehículo: {data['vehicle_type']}")
        
        # Resumen ejecutivo
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(colors.darkgreen)
        c.drawString(50, height - 190, "RESUMEN EJECUTIVO")
        
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.black)
        c.drawString(70, height - 215, f"• Plan Total: {data['totales']['plan_total']:.2f} litros")
        c.drawString(70, height - 235, f"• Consumo Real: {data['totales']['real_total']:.2f} litros")
        c.drawString(70, height - 255, f"• Diferencia: {data['totales']['diferencia_total']:.2f} litros")
        c.drawString(70, height - 275, f"• % Cumplimiento: {data['totales']['porcentaje_cumplimiento']:.1f}%")
        
        # Estado general
        estado_general = "EXCESO" if data['totales']['diferencia_total'] > 0 else "AHORRO" if data['totales']['diferencia_total'] < 0 else "EXACTO"
        color_estado = colors.red if estado_general == "EXCESO" else colors.green if estado_general == "AHORRO" else colors.blue
        
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(color_estado)
        c.drawString(70, height - 300, f"• Estado General: {estado_general}")
        
        # Tabla detallada
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.darkblue)
        c.drawString(50, height - 340, "DETALLE POR VEHÍCULO")
        
        # Encabezados de la tabla
        headers = [
            'Vehículo', 'Matrícula', 'Tipo', 'Plan (L)', 'Real (L)', 
            'Diferencia (L)', '% Cumplimiento', 'Estado'
        ]
        
        # Datos para la tabla
        table_data = [headers]
        
        # Añadir datos de comparaciones
        for comp in data['comparaciones']:
            row = [
                comp['vehiculo'][:15],  # Truncar nombre si es muy largo
                comp['matricula'],
                comp['tipo'],
                f"{comp['plan_combustible']:.1f}",
                f"{comp['real_combustible']:.1f}",
                f"{comp['diferencia']:.1f}",
                f"{comp['porcentaje_cumplimiento']:.1f}%",
                comp['estado']
            ]
            table_data.append(row)
        
        # Añadir fila de totales
        total_row = [
            'TOTALES',
            '',
            '',
            f"{data['totales']['plan_total']:.1f}",
            f"{data['totales']['real_total']:.1f}",
            f"{data['totales']['diferencia_total']:.1f}",
            f"{data['totales']['porcentaje_cumplimiento']:.1f}%",
            estado_general
        ]
        table_data.append(total_row)
        
        # Crear la tabla
        table = Table(table_data, colWidths=[80, 60, 50, 50, 50, 60, 70, 50])
        
        # Estilo de la tabla
        style = TableStyle([
            # Encabezado
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Datos
            ('ALIGN', (3, 1), (-2, -2), 'RIGHT'),  # Números alineados a la derecha
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 8),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            
            # Fila de totales
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 9),
            
            # Colores condicionales para el estado
            ('TEXTCOLOR', (-1, 1), (-1, -2), colors.black),
        ])
        
        # Aplicar colores según el estado
        for i, comp in enumerate(data['comparaciones'], 1):
            if comp['estado'] == 'Exceso':
                style.add('TEXTCOLOR', (-1, i), (-1, i), colors.red)
            elif comp['estado'] == 'Ahorro':
                style.add('TEXTCOLOR', (-1, i), (-1, i), colors.green)
            else:
                style.add('TEXTCOLOR', (-1, i), (-1, i), colors.blue)
        
        table.setStyle(style)
        
        # Dibujar la tabla
        table.wrapOn(c, width - 100, height)
        table.drawOn(c, 50, height - 370 - len(table_data) * 25)
        
        # Pie de página
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.grey)
        c.drawString(50, 50, f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} por {self.env.user.name}")
        c.drawRightString(width - 50, 50, f"Página 1")
        
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
    
    def action_view_data(self):
        """Ver datos en pantalla"""
        self.ensure_one()
        
        # Obtener datos para mostrar
        data = self._get_report_data()
        
        # Crear registros temporales para mostrar en vista tree
        plan_vs_real_lines = []
        for comp in data['comparaciones']:
            plan_vs_real_lines.append((0, 0, {
                'vehicle_name': comp['vehiculo'],
                'license_plate': comp['matricula'],
                'vehicle_type': comp['tipo'],
                'planned_fuel': comp['plan_combustible'],
                'real_fuel': comp['real_combustible'],
                'difference': comp['diferencia'],
                'compliance_percentage': comp['porcentaje_cumplimiento'],
                'status': comp['estado']
            }))
        
        # Actualizar el registro con las líneas
        self.write({
            'plan_vs_real_line_ids': [(5, 0, 0)] + plan_vs_real_lines
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.plan.vs.real.report',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'},
        }
