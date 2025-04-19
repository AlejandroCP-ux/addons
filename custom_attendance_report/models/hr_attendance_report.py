from odoo import models, fields, api

class HRAttendanceCustom(models.Model):
    _name = "hr.attendance.custom"
    _description = "Reporte de Asistencia Personalizado"
    _auto = False

    employee_id = fields.Many2one("hr.employee", string="Empleado", readonly=True)
    department_id = fields.Many2one("hr.department", string="Departamento", readonly=True)
    date = fields.Date(string="Fecha", readonly=True)
    total_worked = fields.Float(string="Tiempo trabajado", readonly=True)
    checkin_morning = fields.Char(string="Entrada Mañana", readonly=True)
    checkout_morning = fields.Char(string="Salida Mañana", readonly=True)
    checkin_afternoon = fields.Char(string="Entrada Tarde", readonly=True)
    checkout_afternoon = fields.Char(string="Salida Tarde", readonly=True)
    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW hr_attendance_custom AS (
                SELECT 
                    row_number() OVER () AS id,
                    he.id AS employee_id,
                    he.department_id,
                    date(((ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)) AS date,
                    ROUND(sum(ha.worked_hours)) as total_worked,
                    to_char(min(
                        CASE
                            WHEN ((ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time >= '07:00:00'::time AND ((ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time <= '09:00:00'::time THEN (ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz
                            ELSE NULL::timestamp with time zone
                        END), 'HH24:MI'::text) AS checkin_morning,
                    to_char(max(
                        CASE
                            WHEN ((ha.check_out AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time >= '11:30:00'::time AND ((ha.check_out AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time <= '12:20:00'::time THEN (ha.check_out AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz
                            ELSE NULL::timestamp with time zone
                        END), 'HH24:MI'::text) AS checkout_morning,
                    to_char(min(
                        CASE
                            WHEN ((ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time >= '12:26:00'::time AND ((ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time <= '13:00:00'::time THEN (ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz
                            ELSE NULL::timestamp with time zone
                        END), 'HH24:MI'::text) AS checkin_afternoon,
                    to_char(max(
                        CASE
                            WHEN ((ha.check_out AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time >= '15:30:00'::time AND ((ha.check_out AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)::time <= '18:00:00'::time THEN (ha.check_out AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz
                            ELSE NULL::timestamp with time zone
                        END), 'HH24:MI'::text) AS checkout_afternoon
                    FROM 
                        hr_attendance ha
                    JOIN 
                        hr_employee he ON ha.employee_id = he.id
                    JOIN 
                        resource_calendar rc ON he.resource_calendar_id = rc.id
                    GROUP BY 
                        he.id, he.department_id, rc.tz, (date(((ha.check_in AT TIME ZONE 'UTC'::text) AT TIME ZONE rc.tz)))
        )
        """)
