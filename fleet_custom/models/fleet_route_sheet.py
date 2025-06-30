# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date
import base64
import io
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

class FleetRouteSheet(models.Model):
    _name = 'fleet.route.sheet'
    _description = 'Hojas de Ruta de Vehículos'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'

    name = fields.Char(string='Hoja de Ruta No.', required=True, copy=False, default='Nuevo', tracking=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, tracking=True)
    vehicle_type = fields.Selection([
        ('tractivo', 'Tractivo'),
        ('arrastre', 'Arrastre'),
    ], string='Tipo', default='tractivo', tracking=True)
    vehicle_brand = fields.Char(string='Marca', related='vehicle_id.model_id.brand_id.name', readonly=True)
    vehicle_capacity = fields.Char(string='Capacidad', tracking=True)
    vehicle_number = fields.Char(string='Número', tracking=True)
    license_plate = fields.Char(string='Matrícula', related='vehicle_id.license_plate', readonly=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True, tracking=True)
    enabled_by = fields.Many2one('res.partner', string='Habilitada por', tracking=True, required=True, 
                            help='Persona que habilita la hoja de ruta')
    entity = fields.Char(string='Entidad', tracking=True, required=True)
    organism = fields.Char(string='Organismo', tracking=True, required=True)
    driver_id = fields.Many2one('res.partner', string='Conductor', related='vehicle_id.driver_id', readonly=True)
    driver_license = fields.Char(string='Licencia No.', tracking=True, required=True)
    signature = fields.Binary(string='Firma', attachment=True, tracking=True)
    signature_filename = fields.Char(string='Nombre del archivo de firma')
    authorized_service = fields.Char(string='Servicio Autorizado', tracking=True, required=True)
    available_kilometers = fields.Float(string='Kilómetros Disponibles', related='vehicle_id.available_kilometers', readonly=True)
    cupo = fields.Char(string='Cupo', tracking=True)
    parqueo = fields.Char(string='Parqueo', tracking=True)
    total_kilometers = fields.Float(string='Total Kilómetros', compute='_compute_totals', store=True, tracking=True)
    total_trips = fields.Integer(string='Cantidad de Viajes', compute='_compute_totals', store=True, tracking=True)
    trip_ids = fields.One2many('fleet.route.sheet.trip', 'route_sheet_id', string='Viajes', tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('cancelled', 'Cancelada')
    ], string='Estado', default='draft', tracking=True)
    cancelled = fields.Boolean(string='Cancelada', default=False, tracking=True)
    pdf_file = fields.Binary(string='Archivo PDF', attachment=True)
    pdf_filename = fields.Char(string='Nombre del archivo PDF')
    
    # Campos para control de mantenimiento
    maintenance_alert = fields.Boolean(string='Alerta de Mantenimiento', related='vehicle_id.maintenance_alert', readonly=True)
    ficav_alert = fields.Boolean(string='Alerta de FICAV', related='vehicle_id.ficav_alert', readonly=True)
    ficav_expiry_date = fields.Date(string='Vencimiento FICAV', related='vehicle_id.ficav_expiry_date', readonly=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.route.sheet') or 'Nuevo'
        return super(FleetRouteSheet, self).create(vals_list)
    
    @api.depends('trip_ids.kilometers', 'trip_ids')
    def _compute_totals(self):
        for sheet in self:
            sheet.total_kilometers = sum(trip.kilometers for trip in sheet.trip_ids)
            sheet.total_trips = len(sheet.trip_ids)
    
    def action_confirm(self):
        for record in self:
            if not record.trip_ids:
                raise ValidationError(_("No puede confirmar una hoja de ruta sin viajes."))
            
            # Verificar si hay suficientes kilómetros disponibles
            if record.vehicle_id.available_kilometers < record.total_kilometers:
                raise ValidationError(_("No hay suficientes kilómetros disponibles para este vehículo. Disponibles: %s km, Requeridos: %s km") % 
                                     (record.vehicle_id.available_kilometers, record.total_kilometers))
            
            # Actualizar kilómetros disponibles y odómetro del vehículo
            record.vehicle_id.write({
                'available_kilometers': record.vehicle_id.available_kilometers - record.total_kilometers,
                'odometer': record.vehicle_id.odometer + record.total_kilometers
            })
            
            # Verificar si se necesita programar mantenimiento
            if record.vehicle_id.available_kilometers <= 500:
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'note': _('El vehículo %s necesita mantenimiento pronto. Kilómetros disponibles: %s') % 
                            (record.vehicle_id.name, record.vehicle_id.available_kilometers),
                    'user_id': self.env.user.id,
                    'res_id': record.vehicle_id.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'fleet.vehicle')], limit=1).id,
                })
            
            record.write({'state': 'confirmed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled', 'cancelled': True})
    
    def action_draft(self):
        self.write({'state': 'draft', 'cancelled': False})
    
    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date > fields.Date.today():
                raise ValidationError(_("La fecha de la hoja de ruta no puede ser futura."))
    
    @api.constrains('vehicle_id')
    def _check_vehicle(self):
        for record in self:
            if not record.vehicle_id.has_route_sheet:
                raise ValidationError(_("El vehículo seleccionado no está configurado para usar hojas de ruta. Por favor, active la opción 'Posee Hoja de Ruta' en la ficha del vehículo."))
            
            # Verificar alertas de mantenimiento y FICAV
            if record.vehicle_id.maintenance_status == 'overdue':
                raise ValidationError(_("El vehículo %s ha excedido el límite de kilómetros para mantenimiento. Por favor, programe un mantenimiento antes de continuar.") % record.vehicle_id.name)
            
            if record.vehicle_id.ficav_status == 'expired':
                raise ValidationError(_("El FICAV del vehículo %s ha vencido. Por favor, renueve el FICAV antes de continuar.") % record.vehicle_id.name)
    
    @api.constrains('trip_ids')
    def _check_trips(self):
        for record in self:
            if record.state != 'draft' and record.trip_ids:
                for trip in record.trip_ids:
                    if trip.create_date and trip.create_date > fields.Datetime.now() - fields.Datetime.from_string(fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')).replace(hour=0, minute=0, second=0, microsecond=0):
                        raise ValidationError(_("No puede añadir viajes a una hoja de ruta que no está en estado borrador."))
    
    def write(self, vals):
        # Verificar si se está intentando modificar una hoja de ruta confirmada o cancelada
        for record in self:
            if record.state in ['confirmed', 'cancelled'] and any(field not in ['state', 'pdf_file', 'pdf_filename'] for field in vals.keys()):
                raise ValidationError(_("No puede modificar una hoja de ruta que está confirmada o cancelada."))
        return super(FleetRouteSheet, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_("No puede eliminar una hoja de ruta que no está en estado borrador."))
        return super(FleetRouteSheet, self).unlink()
    
    def action_generate_pdf(self):
        for record in self:
            # Crear un buffer para el PDF
            buffer = io.BytesIO()
            
            # Crear el PDF
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # Título
            c.setFont("Helvetica-Bold", 16)
            c.drawString(30, height - 40, f"Hoja de Ruta No. {record.name}")
            
            # Información del vehículo
            c.setFont("Helvetica-Bold", 12)
            c.drawString(30, height - 70, "Información del Vehículo:")
            c.setFont("Helvetica", 10)
            c.drawString(30, height - 90, f"Vehículo: {record.vehicle_id.name}")
            c.drawString(30, height - 110, f"Tipo: {dict(self._fields['vehicle_type'].selection).get(record.vehicle_type)}")
            c.drawString(30, height - 130, f"Marca: {record.vehicle_brand}")
            c.drawString(30, height - 150, f"Capacidad: {record.vehicle_capacity}")
            c.drawString(30, height - 170, f"Número: {record.vehicle_number}")
            c.drawString(30, height - 190, f"Matrícula: {record.license_plate}")
            
            # Información general
            c.setFont("Helvetica-Bold", 12)
            c.drawString(300, height - 70, "Información General:")
            c.setFont("Helvetica", 10)
            c.drawString(300, height - 90, f"Fecha: {record.date}")
            c.drawString(300, height - 110, f"Habilitada por: {record.enabled_by.name if record.enabled_by else ''}")
            c.drawString(300, height - 130, f"Entidad: {record.entity}")
            c.drawString(300, height - 150, f"Organismo: {record.organism}")
            c.drawString(300, height - 170, f"Conductor: {record.driver_id.name}")
            c.drawString(300, height - 190, f"Licencia No.: {record.driver_license}")
            
            # Información adicional
            c.setFont("Helvetica", 10)
            c.drawString(30, height - 220, f"Servicio Autorizado: {record.authorized_service}")
            c.drawString(30, height - 240, f"Kilómetros Disponibles: {record.available_kilometers}")
            c.drawString(300, height - 220, f"Cupo: {record.cupo}")
            c.drawString(300, height - 240, f"Parqueo: {record.parqueo}")
            
            # Tabla de viajes
            if record.trip_ids:
                data = [['Fecha', 'Origen', 'Destino', 'Ruta', 'Hora Salida', 'Hora Llegada', 'Tiempo', 'Kms Salida', 'Kms Llegada', 'Total Kms', 'Conductor', 'Pasajeros']]
                
                for trip in record.trip_ids:
                    data.append([
                        trip.date.strftime('%d/%m/%Y') if trip.date else '',
                        trip.origin,
                        trip.destination,
                        trip.authorized_route,
                        trip.departure_time.strftime('%H:%M') if trip.departure_time else '',
                        trip.arrival_time.strftime('%H:%M') if trip.arrival_time else '',
                        f"{trip.travel_time:.2f}",
                        f"{trip.departure_odometer:.1f}",
                        f"{trip.arrival_odometer:.1f}",
                        f"{trip.kilometers:.1f}",
                        trip.driver_number,
                        f"{trip.passenger_count}"
                    ])
                
                # Añadir fila de totales
                data.append(['Totales', '', '', '', '', '', '', '', '', f"{record.total_kilometers:.1f}", '', f"{sum(trip.passenger_count for trip in record.trip_ids)}"])
                
                table = Table(data, colWidths=[50, 50, 50, 50, 50, 50, 40, 50, 50, 50, 50, 50])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                
                table.wrapOn(c, width - 60, height)
                table.drawOn(c, 30, height - 500)
            
            # Firma
            c.setFont("Helvetica", 10)
            c.drawString(30, 100, "Firma del Conductor:")
            c.line(30, 80, 200, 80)
            
            if record.signature:
                try:
                    image_data = base64.b64decode(record.signature)
                    image = Image.open(io.BytesIO(image_data))
                    image_path = f"/tmp/signature_{record.id}.png"
                    image.save(image_path)
                    c.drawImage(image_path, 30, 30, width=150, height=50)
                except Exception as e:
                    c.drawString(30, 60, "Error al cargar la firma")
            
            # Guardar el PDF
            c.save()
            
            # Obtener el valor del PDF
            pdf = buffer.getvalue()
            buffer.close()
            
            # Guardar el PDF en el registro
            record.write({
                'pdf_file': base64.b64encode(pdf),
                'pdf_filename': f"Hoja_de_Ruta_{record.name}.pdf"
            })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/pdf_file/{self.pdf_filename}?download=true',
            'target': 'self',
        }

class FleetRouteSheetTrip(models.Model):
    _name = 'fleet.route.sheet.trip'
    _description = 'Viajes de Hoja de Ruta'
    _order = 'date, departure_time'
    
    route_sheet_id = fields.Many2one('fleet.route.sheet', string='Hoja de Ruta', required=True, ondelete='cascade')
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True)
    origin = fields.Char(string='Origen', required=True)
    destination = fields.Char(string='Destino', required=True)
    authorized_route = fields.Char(string='Ruta Autorizada', required=True)
    departure_time = fields.Datetime(string='Hora Salida', required=True)
    arrival_time = fields.Datetime(string='Hora Llegada', required=True)
    travel_time = fields.Float(string='Tiempo en horas', compute='_compute_travel_time', store=True)
    departure_odometer = fields.Float(string='Kms Odómetro Salida', required=True)
    arrival_odometer = fields.Float(string='Kms Odómetro Llegada', required=True)
    kilometers = fields.Float(string='Total Kms', compute='_compute_kilometers', store=True)
    driver_number = fields.Char(string='Nro conduce o Carta porte')
    passenger_count = fields.Integer(string='Cantidad de pasajeros', default=0)
    
    @api.depends('departure_time', 'arrival_time')
    def _compute_travel_time(self):
        for trip in self:
            if trip.departure_time and trip.arrival_time:
                delta = trip.arrival_time - trip.departure_time
                trip.travel_time = delta.total_seconds() / 3600
            else:
                trip.travel_time = 0.0
    
    @api.depends('departure_odometer', 'arrival_odometer')
    def _compute_kilometers(self):
        for trip in self:
            trip.kilometers = trip.arrival_odometer - trip.departure_odometer if trip.arrival_odometer > trip.departure_odometer else 0.0
    
    @api.constrains('departure_odometer', 'arrival_odometer')
    def _check_odometer(self):
        for trip in self:
            if trip.arrival_odometer < trip.departure_odometer:
                raise ValidationError(_("El kilometraje de llegada no puede ser menor que el kilometraje de salida."))
    
    @api.constrains('departure_time', 'arrival_time')
    def _check_times(self):
        for trip in self:
            if trip.departure_time and trip.arrival_time and trip.departure_time >= trip.arrival_time:
                raise ValidationError(_("La hora de llegada debe ser posterior a la hora de salida."))
    
    @api.constrains('date')
    def _check_date(self):
        for trip in self:
            if trip.date > fields.Date.today():
                raise ValidationError(_("La fecha del viaje no puede ser futura."))
            
            # Verificar que la fecha del viaje coincida con la fecha de la hoja de ruta
            if trip.route_sheet_id and trip.date != trip.route_sheet_id.date:
                raise ValidationError(_("La fecha del viaje debe coincidir con la fecha de la hoja de ruta."))
    
    @api.constrains('passenger_count')
    def _check_passenger_count(self):
        for trip in self:
            if trip.passenger_count < 0:
                raise ValidationError(_("La cantidad de pasajeros no puede ser negativa."))
    
    def write(self, vals):
        # Verificar si se está intentando modificar un viaje de una hoja de ruta confirmada o cancelada
        for record in self:
            if record.route_sheet_id.state in ['confirmed', 'cancelled']:
                raise ValidationError(_("No puede modificar un viaje de una hoja de ruta que está confirmada o cancelada."))
        return super(FleetRouteSheetTrip, self).write(vals)
    
    def unlink(self):
        for record in self:
            if record.route_sheet_id.state != 'draft':
                raise ValidationError(_("No puede eliminar un viaje de una hoja de ruta que no está en estado borrador."))
        return super(FleetRouteSheetTrip, self).unlink()
