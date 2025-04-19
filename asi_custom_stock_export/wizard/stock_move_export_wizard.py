from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import UserError
import zipfile
import tempfile
import base64
import os

class stockmoveExportWizard(models.TransientModel):
    _name = 'stock.move.export.wizard'
    _description = 'stock move Export Wizard'
        
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res_ids = self._context.get('active_ids')

        stock_moves = self.env['stock.move'].browse(res_ids)
        if not stock_moves:
            raise UserError(_("You can only send stock moves."))

        res.update({
            'stock_move_ids': [Command.set(res_ids)],        
        })
        return res

    stock_move_ids = fields.Many2many('stock.move', string='Stock Moves')   
    z_file = fields.Many2one('ir.attachment', compute='_compute_zip_file', store=True)

    @api.depends('stock_move_ids')
    def _compute_zip_file(self):
        for record in self:
          temp_zip = tempfile.mktemp(suffix='.zip', prefix='movimientos')
          with zipfile.ZipFile(temp_zip, 'w') as zip_file:            
            for stock_move in record.stock_move_ids:
                file_content = ''        
                file_content += '[Obligacion]\n'
                file_content += 'Concepto=Obligacion por Factura Emitida\n'
                file_content += 'Tipo={7DE34F15-C9BA-4FE0-AEE6-B5E85ADB84DC}\n'
                file_content += 'Unidad=01\n'
                #file_content += 'Entidad={}\n'.format(stock_move.partner_id.ref or '').replace(".","")
                #file_content += 'Numero={}\n'.format(stock_move.name or '')
                #file_content += 'Fechaemi={}\n'.format(stock.move.stock.move_date.strftime('%d/%m/%Y') if stock.move.stock.move_date else '')
                #file_content += 'Fechaemi=27/10/2023\n'
                #file_content += 'Descripcion=Documento Importado\n'
                #file_content += 'Descripcion=Cliente: {} '.format(stock.move.partner_id.name or '')
                #file_content += ' Ref:{}'.format(stock.move.partner_id.ref or '')
                #file_content += ' Equipo:{}'.format(stock.move.team_id.name or '')
                #file_content += 'ImporteMC={:.2f}\n'.format(stock.move.amount_total_signed or '')
                #file_content += 'CuentaMC={}\n'.format(stock.move.partner_id.property_account_receivable_id.code.replace("."," ") or '')
                #file_content += '[Contrapartidas]\n'
                #file_content += 'Concepto=107\n'
                #file_content += 'Importe={:.2f}\n'.format(stock.move.amount_total_signed or '')
                file_content += '{\n'
                #lines_data = {}
                #for line in stock.move.stock.move_line_ids.filtered(lambda l: l.display_type not in ['line_section','line_note']):                    
                #    account_code = line.account_id.code.replace("."," ")
                #    if account_code in lines_data:
                #        lines_data[account_code] += line.price_subtotal
                #    else:
                #        lines_data[account_code] = line.price_subtotal
                #for account_code, subtotal in lines_data.items():
                #    file_content += '{}|CUP|{:.2f}\n'.format(account_code or '', subtotal or '')
                #file_content += '}\n'
                file_name = '{}.obl'.format('-'.join(stock.move.reference.split('/')))              
                temp = tempfile.mktemp(suffix='.obl')            
                with open(temp, 'w') as file:
                    file.write(file_content)
                zip_file.write(temp, arcname=file_name)              
                os.remove(temp)

          with open(temp_zip, 'rb') as f:
            attachment = self.env['ir.attachment'].create({
                'name': 'movimientos_stock.zip',
                'type': 'binary',
                'datas': base64.b64encode(f.read()),
                'res_model': 'stock.move.export.wizard',
                'res_id': record.id,
                'mimetype': 'application/zip'
            })
            record.z_file = attachment.id          
          
    def save_ok(self):
      return True