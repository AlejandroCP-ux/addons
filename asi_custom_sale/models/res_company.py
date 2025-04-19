from odoo import api, models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    reeup_code = fields.Char(compute='_compute_address', inverse='_inverse_reeup_code')
    ref = fields.Char(compute='_compute_address', inverse='_inverse_ref')
    bank_accounts = fields.Text(compute='_compute_address', inverse='_inverse_bank_accounts')
   
    def _inverse_reeup_code(self):
        for company in self:
            company.partner_id.reeup_code = company.reeup_code
            
    def _inverse_ref(self):
        for company in self:
            company.partner_id.ref = company.ref        
            
            
    def _inverse_bank_accounts(self):
        for company in self:
            company.partner_id.bank_accounts = company.bank_accounts               
    
            
    def _get_company_address_field_names(self):
        """ Return a list of fields coming from the address partner to match
        on company address fields. Fields are labeled same on both models. """
        address_fields = super(ResCompany, self)._get_company_address_field_names()
        # Añadimos el campo 'ref' a la lista
        address_fields.append('reeup_code')
        address_fields.append('bank_accounts')
        return address_fields    


    def _default_company_details(self):
        # Define tu propio valor predeterminado en HTML
        return """
            <p>Nombre de la empresa: <strong>Mi Empresa</strong></p>
            <p>Dirección: Calle Principal #123</p>
            <p>Teléfono: +123 456 7890</p>
            <p>Email: info@miempresa.com</p>
        """

    company_details = fields.Html(
        string="Detalles de la empresa",
        default=_default_company_details,
        readonly=False,
    )                      