from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import UserError
import zipfile
import tempfile
import base64
import os

class InvoiceExportWizard(models.TransientModel):
    _name = 'invoice.export.wizard'
    _description = 'Invoice Export Wizard'
    
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res_ids = self._context.get('active_ids')

        invoices = self.env['account.move'].browse(res_ids).filtered(lambda move: move.is_invoice(include_receipts=True))
        if not invoices:
            raise UserError(_("You can only send invoices."))

        res.update({
            'invoice_ids': [Command.set(res_ids)],        
        })
        return res
    
    invoice_ids = fields.Many2many('account.move', string='Invoices')
    z_file = fields.Many2one('ir.attachment', compute='_compute_zip_file', store=True)

    @api.depends('invoice_ids')
    def _compute_zip_file(self):
        for record in self:
          temp_zip = tempfile.mktemp(suffix='.zip', prefix='obligaciones')
          with zipfile.ZipFile(temp_zip, 'w') as zip_file:            
            for invoice in record.invoice_ids:
                file_content = ''        
                file_content += '[Obligacion]\n'
                file_content += 'Concepto=Obligacion por Factura Emitida\n'
                file_content += 'Tipo={7DE34F15-C9BA-4FE0-AEE6-B5E85ADB84DC}\n'
                file_content += 'Unidad=01\n'
                file_content += 'Entidad={}\n'.format(invoice.partner_id.ref or '').replace(".","")
                file_content += 'Numero={}\n'.format(invoice.name or '')
                file_content += 'Fechaemi={}\n'.format(invoice.invoice_date.strftime('%d/%m/%Y') if invoice.invoice_date else '')
                #file_content += 'Fechaemi=27/10/2023\n'
                #file_content += 'Descripcion=Documento Importado\n'
                file_content += 'Descripcion=Cliente: {} '.format(invoice.partner_id.name or '')
                file_content += ' Ref:{}'.format(invoice.partner_id.ref or '')
                file_content += ' Reeup:{}'.format(invoice.partner_id.reeup_code or '')
                file_content += ' Equipo:{}'.format(invoice.team_id.name or '')
                file_content += ' Ctto:{}\n'.format(invoice.partner_id.asi_contract or '')
                file_content += 'ImporteMC={:.2f}\n'.format(invoice.amount_total_signed or '')
                file_content += 'CuentaMC={}\n'.format(invoice.partner_id.property_account_receivable_id.code or '')
                file_content += '[Contrapartidas]\n'
                file_content += 'Concepto=107\n'
                file_content += 'Importe={:.2f}\n'.format(invoice.amount_total_signed or '')
                file_content += '{\n'
                lines_data = {}
                for line in invoice.invoice_line_ids.filtered(lambda l: l.display_type not in ['line_section','line_note']):                    
                    account_code = line.account_id.code
                    if account_code in lines_data:
                        lines_data[account_code] += line.price_subtotal
                    else:
                        lines_data[account_code] = line.price_subtotal
                for account_code, subtotal in lines_data.items():
                    #file_content += '{}|CUP|{:.2f}\n'.format(account_code or '', subtotal or '')
                    file_content += '{}|CUP|{:.2f}\n'.format(account_code or '', float(subtotal) if isinstance(subtotal, (int, float)) else subtotal)
                file_content += '}\n'
                file_name = '{}.obl'.format('-'.join(invoice.name.split('/')))              
                temp = tempfile.mktemp(suffix='.obl')            
                with open(temp, 'w') as file:
                    file.write(file_content)
                zip_file.write(temp, arcname=file_name)              
                os.remove(temp)

          with open(temp_zip, 'rb') as f:
            attachment = self.env['ir.attachment'].create({
                'name': 'obligaciones.zip',
                'type': 'binary',
                'datas': base64.b64encode(f.read()),
                'res_model': 'invoice.export.wizard',
                'res_id': record.id,
                'mimetype': 'application/zip'
            })
            record.z_file = attachment.id          
          
    def save_ok(self):
      return True