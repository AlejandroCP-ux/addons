from odoo import api, SUPERUSER_ID

def uninstall_hook(cr, registry):
   env = api.Environment(cr, SUPERUSER_ID, {})
   env['ir.attachment'].search([('name', 'ilike', 'web.assets_')]).unlink()

def post_init_hook(cr, registry):
   env = api.Environment(cr, SUPERUSER_ID, {})
   env['ir.attachment'].search([('name', 'ilike', 'web.assets_')]).unlink()