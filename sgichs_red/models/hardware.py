# -*- coding: utf-8 -*-
from odoo import models, fields, api
import os
import shlex
import subprocess
import re
import logging

_logger = logging.getLogger(__name__)

class Hardware(models.Model):
    _inherit = 'it.asset.hardware'

    ip_ids = fields.Many2many(
        'it.ip.address',
        'hardware_ip_rel',
        'hardware_id',
        'ip_id',
        string='Direcciones IP'
    )
    connection_status = fields.Selection(
        selection=[
            ('online', 'Online'),
            ('offline', 'Offline'),
            ('unreachable', 'Inalcanzable'),
            ('pending', 'Pendiente'),
            ('unknown', 'Desconocido'),
        ],
        string='Estado de Conexión',
        default='pending',
        readonly=True,
        tracking=True
    )
    last_ping_time = fields.Datetime(string='Último Ping', readonly=True)
    ping_history_ids = fields.One2many(
        'it.hardware.ping.history',
        'hardware_id',
        string='Historial de Ping'
    )

    def _get_first_ip(self):
        self.ensure_one()
        return self.ip_ids[0].address if self.ip_ids else None

    def _do_ping(self, ip_address):
        try:
            param = '-n 1 -w 2000' if os.name == 'nt' else '-c 1 -W 2'
            command = f"ping {param} {shlex.quote(ip_address)}"
            output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, universal_newlines=True, timeout=3)
            if "TTL=" in output or "ttl=" in output:
                time_match = re.search(r'time[=<>](\d+\.?\d*)', output)
                return 'online', float(time_match.group(1)) if time_match else 0.0
            return 'unreachable', 0.0
        except subprocess.CalledProcessError:
            return 'offline', 0.0
        except Exception as e:
            _logger.error(f"Error en ping a {ip_address}: {str(e)}")
            return 'unknown', 0.0

    def update_connection_status(self):
        for device in self:
            ip_address = device._get_first_ip()
            if not ip_address:
                device.connection_status = 'unknown'
                continue

            status, response_time = device._do_ping(ip_address)
            
            device.write({
                'connection_status': status,
                'last_ping_time': fields.Datetime.now(),
            })

            self.env['it.hardware.ping.history'].create({
                'hardware_id': device.id,
                'status': status,
                'response_time_ms': response_time,
            })

    def action_manual_ping(self):
        self.ensure_one()
        self.update_connection_status()

    @api.model
    def cron_ping_devices(self):
        _logger.info("Iniciando tarea programada: Ping a dispositivos de TI...")
        devices_to_ping = self.search([('status', '=', 'active')])
        devices_to_ping.update_connection_status()
        _logger.info(f"Ping completado para {len(devices_to_ping)} dispositivos.")