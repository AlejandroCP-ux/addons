from odoo import http
from odoo.http import request
import os

class InvoiceExportController(http.Controller):

    @http.route('/invoice/export', type='http', auth='user')
    def export_invoices(self, **post):
        invoice_ids = post.get('invoice_ids', '').split(',')
        if invoice_ids:
            invoices = request.env['account.move'].browse([int(id) for id in invoice_ids])
            file_content = self.generate_file_content(invoices)
            file_name = self.generate_file_name(invoices[0])
            file_path = '/tmp/' + file_name
            with open(file_path, 'w') as file:
                file.write(file_content)
            return request.env['ir.http'].send_file(file_path, filename=file_name)
        else:
            return http.request.not_found()

    def generate_file_content(self, invoices):
        file_content = ''
        for invoice in invoices:
            file_content += '[Obligacion1]\n'
            file_content += 'Entidad={}\n'.format(invoice.partner_id.internal_reference or '')
            file_content += 'Numero={}\n'.format(invoice.name or '')
            file_content += 'Fechaemi={}\n'.format(invoice.invoice_date.strftime('%m/%d/%Y') if invoice.invoice_date else '')
            file_content += 'Descripcion=Documento Importado\n'
            file_content += 'Fecharec=\n'
            file_content += 'ImporteMC={}\n'.format(invoice.amount_total_signed or '')
            file_content += 'CuentaMC={}\n'.format(invoice.partner_id.property_account_receivable_id.code or '')
            file_content += '[Contrapartidas]\n'
            file_content += 'Concepto=107\n'
            file_content += 'Importe={}\n'.format(invoice.amount_total_signed or '')
            for line in invoice.invoice_line_ids:
                file_content += '{}|CUP|{}\n'.format(line.account_id.code or '', line.price_subtotal_signed or '')
            file_content += '\n'
        return file_content

    def generate_file_name(self, invoice):
        return '{}.obl'.format(invoice.name.replace('/', '_'))