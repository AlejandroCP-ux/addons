# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _

class FleetActivityReportView(models.Model):
    _name = 'fleet.activity.report.view'
    _description = 'Vista de Informe de Nivel de Actividad por Equipos'
    _auto = False
    _order = 'fuel_type, activity_type, license_plate'

    fuel_type = fields.Char(string='Portador (Combustible)', readonly=True)
    activity_type = fields.Char(string='Tipo de Actividad', readonly=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', readonly=True)
    license_plate = fields.Char(string='Matrícula', readonly=True)
    total_kilometers = fields.Float(string='Nivel de Actividad', readonly=True)
    unit_measure = fields.Char(string='Unidad de Medida', readonly=True)
    date_from = fields.Date(string='Fecha Desde', readonly=True)
    date_to = fields.Date(string='Fecha Hasta', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () AS id,
                    CASE 
                        WHEN fv.custom_fuel_type = 'gasolina' THEN 'Gasolina Motor (83 Octanos)'
                        WHEN fv.custom_fuel_type = 'diesel' THEN 'Combustible Diesel Regular'
                        ELSE COALESCE(fv.custom_fuel_type, 'Desconocido')
                    END AS fuel_type,
                    COALESCE(fat.name, 'Sin Actividad') AS activity_type,
                    rs.vehicle_id,
                    fv.license_plate,
                    SUM(rs.total_kilometers) AS total_kilometers,
                    CASE 
                        WHEN fv.is_technological THEN 'Horas'
                        ELSE 'Km.'
                    END AS unit_measure,
                    MIN(rs.date) AS date_from,
                    MAX(rs.date) AS date_to
                FROM fleet_route_sheet rs
                JOIN fleet_vehicle fv ON rs.vehicle_id = fv.id
                LEFT JOIN fleet_activity_type fat ON fv.custom_activity_type_id = fat.id
                WHERE rs.state = 'confirmed'
                GROUP BY fv.custom_fuel_type, fat.name, rs.vehicle_id, fv.license_plate, fv.is_technological
            )
        """ % self._table)

class FleetConsumptionIndexReportView(models.Model):
    _name = 'fleet.consumption.index.report.view'
    _description = 'Vista de Informe de Índice de Consumo'
    _auto = False
    _order = 'license_plate'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', readonly=True)
    license_plate = fields.Char(string='Matrícula', readonly=True)
    total_kilometers = fields.Float(string='Nivel Actividad', readonly=True)
    unit_measure = fields.Char(string='Unidad de medida', readonly=True)
    previous_fuel = fields.Float(string='Litros en tanque mes anterior', readonly=True)
    fuel_consumed = fields.Float(string='Consumo litros', readonly=True)
    third_party_fuel = fields.Float(string='Comb. de Terceros litros', readonly=True)
    current_fuel = fields.Float(string='Litros en tanque mes actual', readonly=True)
    real_consumption = fields.Float(string='Consumo Real', readonly=True)
    approx_consumption = fields.Float(string='Consumo Aproximado', readonly=True)
    consumption_index = fields.Float(string='Índice Consumo', readonly=True)
    planned_index = fields.Float(string='Índice Plan', readonly=True)
    deviation_percent = fields.Float(string='% Desv.', readonly=True)
    significant_deviation = fields.Char(string='Desv. > 5 %', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () AS id,
                    ffr.vehicle_id,
                    fv.license_plate,
                    ffr.total_kilometers,
                    CASE 
                        WHEN fv.is_technological THEN 'Horas'
                        ELSE 'Km.'
                    END AS unit_measure,
                    ffr.estimated_fuel AS previous_fuel,
                    ffr.total_fuel_consumed AS fuel_consumed,
                    0 AS third_party_fuel,
                    ffr.closing_fuel AS current_fuel,
                    ffr.total_fuel_consumed AS real_consumption,
                    CASE 
                        WHEN COALESCE(fci.current_consumption_index, 0) > 0 
                        THEN ffr.total_kilometers / fci.current_consumption_index
                        ELSE 0
                    END AS approx_consumption,
                    ffr.real_consumption_index AS consumption_index,
                    COALESCE(fci.current_consumption_index, 0) AS planned_index,
                    CASE 
                        WHEN COALESCE(fci.current_consumption_index, 0) > 0 
                        THEN ((ffr.real_consumption_index / fci.current_consumption_index) - 1) * 100
                        ELSE 0
                    END AS deviation_percent,
                    CASE 
                        WHEN ABS(CASE 
                            WHEN COALESCE(fci.current_consumption_index, 0) > 0 
                            THEN ((ffr.real_consumption_index / fci.current_consumption_index) - 1) * 100
                            ELSE 0
                        END) > 5 THEN '*'
                        ELSE ''
                    END AS significant_deviation
                FROM fleet_fuel_record ffr
                JOIN fleet_vehicle fv ON ffr.vehicle_id = fv.id
                LEFT JOIN fleet_consumption_index fci ON ffr.vehicle_id = fci.vehicle_id
                WHERE ffr.state = 'confirmed'
            )
        """ % self._table)
