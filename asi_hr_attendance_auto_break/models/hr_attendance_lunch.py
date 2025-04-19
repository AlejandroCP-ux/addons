# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pytz
import logging
from datetime import datetime
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class HrAttendanceLunch(models.Model):
    """
    Extensión del modelo hr.attendance para gestionar automáticamente los registros de asistencia durante la hora del almuerzo.
    
    Extension of the hr.attendance model to automatically manage attendance records during lunch time.
    """
    _inherit = 'hr.attendance'

    def _get_datetime_with_user_tz(self, dt, employee_tz):
        """
        Convierte una fecha y hora UTC a la zona horaria del empleado.
        
        Converts a UTC datetime to the employee's timezone.
        
        :param dt: Datetime en UTC / UTC datetime
        :param employee_tz: Zona horaria del empleado / Employee timezone
        :return: Datetime en la zona horaria del empleado / Datetime in employee's timezone
        """
        try:
            tz = pytz.timezone(employee_tz or 'UTC')
            dt_utc = pytz.utc.localize(dt)
            return dt_utc.astimezone(tz)
        except Exception as e:
            _logger.error("Error al convertir datetime a zona horaria del empleado: %s", e)
            # En caso de error, devolver el datetime original
            # In case of error, return the original datetime
            return dt
    
    def _get_utc_datetime_from_user_tz(self, dt, hour, minute, employee_tz):
        """
        Crea un datetime UTC a partir de una fecha, hora y zona horaria del empleado.
        
        Creates a UTC datetime from a date, time and employee timezone.
        
        :param dt: Fecha base / Base date
        :param hour: Hora / Hour
        :param minute: Minuto / Minute
        :param employee_tz: Zona horaria del empleado / Employee timezone
        :return: Datetime en UTC / UTC datetime
        """
        try:
            tz = pytz.timezone(employee_tz or 'UTC')
            # Crear datetime en zona horaria del empleado
            # Create datetime in employee timezone
            local_dt = datetime(dt.year, dt.month, dt.day, hour, minute, 0)
            _logger.debug("Datetime local creado: %s en zona horaria %s", local_dt, employee_tz)
            local_dt = tz.localize(local_dt)
            # Convertir a UTC
            # Convert to UTC
            utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
            _logger.debug("Datetime convertido a UTC: %s", utc_dt)
            return utc_dt
        except Exception as e:
            _logger.error("Error al crear datetime UTC desde zona horaria del empleado: %s", e)
            # En caso de error, crear un datetime UTC directamente
            # In case of error, create a UTC datetime directly
            return datetime(dt.year, dt.month, dt.day, hour, minute, 0)
    
    @api.model
    def process_lunch_break_attendances_manual(self):
        """
        Método para ejecutar manualmente el procesamiento de pausas de almuerzo desde la interfaz de usuario.
        
        Method to manually execute lunch break processing from the user interface.
        """
        _logger.error("EJECUTANDO MANUALMENTE EL PROCESO DE PAUSA DE ALMUERZO")
        result = self._process_lunch_break_attendances()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Lunch Break Processing'),
                'message': _('Lunch break processing completed. Check the logs for details.'),
                'sticky': False,
                'type': 'success' if result else 'danger',
            }
        }
    
    @api.model
    def _process_lunch_break_attendances(self):
        """
        Procesa los registros de asistencia para la pausa del almuerzo:
        - Se ejecuta a las 3:00 PM y 5:00 PM (hora del servidor)
        - Busca usuarios con registros abiertos desde la mañana (7:00-11:30 AM)
        - Les cierra ese registro con hora de salida a las 12:00 PM
        - Les crea un nuevo registro con entrada a las 12:30 PM
        
        Process attendance records for lunch break:
        - Runs at 3:00 PM and 5:00 PM (server time)
        - Finds users with open records from the morning (7:00-11:30 AM)
        - Closes those records with a check-out time at 12:00 PM
        - Creates a new record with check-in time at 12:30 PM
        """
        # Forzar un log de error para asegurarnos de que se está ejecutando el método
        # Force an error log to make sure the method is being executed
        _logger.error("=== INICIANDO PROCESO DE PAUSA DE ALMUERZO AUTOMÁTICA ===")
        _logger.error("Hora del servidor: %s", fields.Datetime.now())
        
        try:
            today = fields.Date.today()
            now = fields.Datetime.now()
            
            _logger.error("Fecha actual: %s", today)
            
            # Buscar todos los registros de asistencia abiertos (sin check_out)
            # Find all open attendance records (without check_out)
            domain = [
                ('check_out', '=', False),
            ]
            
            _logger.error("Dominio de búsqueda: %s", domain)
            
            open_attendances = self.search(domain)
            
            _logger.error("Registros de asistencia abiertos encontrados: %d", len(open_attendances))
            
            if not open_attendances:
                _logger.error("No se encontraron registros de asistencia abiertos para procesar.")
                return True
            
            # Forzar un log con los IDs de los registros encontrados
            # Force a log with the IDs of the records found
            attendance_ids = open_attendances.mapped('id')
            _logger.error("IDs de registros abiertos: %s", attendance_ids)
            
            employees_to_process = []
            
            # Verificar cada registro abierto
            # Check each open record
            for attendance in open_attendances:
                employee = attendance.employee_id
                employee_tz = employee.tz or 'UTC'
                
                _logger.error("Procesando empleado: %s (ID: %s), Zona horaria: %s, Check-in: %s", 
                             employee.name, employee.id, employee_tz, attendance.check_in)
                
                try:
                    # Convertir check_in a la zona horaria del empleado
                    # Convert check_in to employee timezone
                    check_in_employee_tz = self._get_datetime_with_user_tz(attendance.check_in, employee_tz)
                    
                    _logger.error("Check-in (Zona horaria del empleado): %s", check_in_employee_tz)
                    _logger.error("Hora: %d, Minuto: %d", check_in_employee_tz.hour, check_in_employee_tz.minute)
                    
                    # Verificar si el check_in está entre 7:00 AM y 11:30 AM
                    # Check if check_in is between 7:00 AM and 11:30 AM
                    if (7 <= check_in_employee_tz.hour < 11 or 
                        (check_in_employee_tz.hour == 11 and check_in_employee_tz.minute <= 30)):
                        _logger.error("Empleado %s califica para procesamiento de pausa de almuerzo", employee.name)
                        employees_to_process.append({
                            'employee': employee,
                            'attendance': attendance,
                            'employee_tz': employee_tz
                        })
                    else:
                        _logger.error("Empleado %s no califica: check-in fuera del rango 7:00-11:30 AM (hora: %d, minuto: %d)", 
                                     employee.name, check_in_employee_tz.hour, check_in_employee_tz.minute)
                except Exception as e:
                    _logger.error("Error al procesar el empleado %s: %s", employee.name, e)
                    import traceback
                    _logger.error(traceback.format_exc())
            
            _logger.error("Empleados que califican para procesamiento: %d", len(employees_to_process))
            
            # Procesar los empleados identificados
            # Process the identified employees
            for emp_data in employees_to_process:
                try:
                    employee = emp_data['employee']
                    attendance = emp_data['attendance']
                    employee_tz = emp_data['employee_tz']
                    
                    _logger.error("Procesando pausa de almuerzo para: %s", employee.name)
                    
                    # Obtener la fecha del check_in
                    # Get the date of check_in
                    check_in_date = self._get_datetime_with_user_tz(attendance.check_in, employee_tz).date()
                    
                    _logger.error("Fecha del check-in: %s", check_in_date)
                    
                    # Crear la hora de salida a las 12:00 PM en la zona horaria del empleado
                    # Create the checkout time at 12:00 PM in the employee's timezone
                    checkout_time_utc = self._get_utc_datetime_from_user_tz(check_in_date, 12, 0, employee_tz)
                    
                    _logger.error("Hora de salida (UTC): %s", checkout_time_utc)
                    
                    # Crear la hora de entrada a las 12:30 PM en la zona horaria del empleado
                    # Create the checkin time at 12:30 PM in the employee's timezone
                    checkin_time_utc = self._get_utc_datetime_from_user_tz(check_in_date, 12, 30, employee_tz)
                    
                    _logger.error("Hora de entrada (UTC): %s", checkin_time_utc)
                    
                    # Actualizar el registro de asistencia existente con la hora de salida
                    # Update the existing attendance record with the checkout time
                    _logger.error("Actualizando registro de asistencia ID: %s con check-out: %s", 
                                attendance.id, checkout_time_utc)
                    
                    attendance.write({
                        'check_out': checkout_time_utc
                    })
                    
                    # Crear un nuevo registro de asistencia con la hora de entrada
                    # Create a new attendance record with the checkin time
                    _logger.error("Creando nuevo registro de asistencia para empleado ID: %s con check-in: %s", 
                                employee.id, checkin_time_utc)
                    
                    new_attendance = self.create({
                        'employee_id': employee.id,
                        'check_in': checkin_time_utc
                    })
                    
                    _logger.error("Nuevo registro de asistencia creado con ID: %s", new_attendance.id)
                    
                    # Registrar mensaje en el log para fines de auditoría
                    # Log message for audit purposes
                    self.env['mail.message'].create({
                        'model': 'hr.attendance',
                        'res_id': attendance.id,
                        'message_type': 'notification',
                        'body': _('Automatic lunch break: Check-out created at 12:00 PM and new check-in at 12:30 PM')
                    })
                    
                    _logger.error("Procesamiento completado para empleado: %s", employee.name)
                except Exception as e:
                    _logger.error("Error al procesar pausa de almuerzo para empleado %s: %s", 
                                 emp_data['employee'].name, e)
                    import traceback
                    _logger.error(traceback.format_exc())
            
            _logger.error("=== PROCESO DE PAUSA DE ALMUERZO AUTOMÁTICA COMPLETADO ===")
            return True
            
        except Exception as e:
            _logger.error("Error general en el proceso de pausa de almuerzo: %s", e)
            # Registrar la traza completa del error
            import traceback
            _logger.error(traceback.format_exc())
            return False

