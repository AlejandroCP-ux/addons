import base64
import xml.etree.ElementTree as ET
import io
import logging

from odoo import _, api, models
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)


class AccountStatementImport(models.TransientModel):
    _inherit = "account.statement.import"


    def identify_bank_statement(self, textstring):
        # segun el campo observaciones, identificamos el tipo de linea de extracto
        # Posibles tipos: Bandec, BPA ...
        tipo = "Bandec"
        if textstring.startswith("[COD_ORIGEN:12]"):
            tipo = "BPA"

        return tipo    

    def extract_mid_str(self, textstring, from_string, to_string):
        # Buscar la posición de inicio
        inicio = textstring.lower().find(from_string.lower())

        # Si no se encuentra , devolver una cadena vacía
        if inicio == -1:
            return ""
        
        # Buscar la posición de fin 
        fin = textstring.lower().find(to_string.lower(), inicio + len(from_string))

        # Si no se encuentra from_string despues de to_string devolver una cadena vacía
        if fin == -1:
            return ""
        
        # Extraer el texto entre from_string y to_string
        result_text = textstring[inicio + len(from_string):fin].strip()
        
        return result_text

    def get_partner(self, value):
        Partner = self.env['res.partner']
        BankAcc = self.env['res.partner.bank']
        name = value.get('name')
        acc_number = value.get('acc_number')
        partner = None
    
        if acc_number:
            # Buscar por número de cuenta bancaria
            bank_account = BankAcc.search([('acc_number', '=', acc_number)], limit=1)
            if bank_account:
                partner = bank_account.partner_id
    
        if not partner and name:
            # Buscar por nombre
            partners = Partner.search([('name', '=', name)])
            if partners:
                partner = partners[0]  # Tomar el primer registro si hay varios
            else:
                # Buscar por titular de cuenta bancaria
                bank_account = BankAcc.search([('acc_holder_name', '=', name)], limit=1)
                partner = bank_account.partner_id
    
        # Devolver el ID si se encuentra un partner, o False si no
        return partner.id if partner else False

    
    def get_partner(self, value):
        Partner = self.env['res.partner']
        BankAcc = self.env['res.partner.bank']
        name = value.get('name')
        acc_number = value.get('acc_number')
        partner = None
        
        if name:
            #looking by name        
            partner = Partner.search([('name', '=', name)])
            
            #looking by acc titular
            if not partner:
                partner = BankAcc.search([('acc_holder_name', '=', name)], limit=1).partner_id

        elif acc_number:
            partner = BankAcc.search([('acc_number', '=', acc_number)], limit=1).partner_id
            
        return partner.id if partner else False

    @api.model
    def _prepare_bandec_transaction_line(self, transaction):
        # Since bandecparse doesn't provide account numbers,
        # we cannot provide the key 'bank_account_id',
        # nor the key 'account_number'
        # If you read odoo10/addons/account_bank_statement_import/
        # account_bank_statement_import.py, it's the only 2 keys
        # we can provide to match a partner.
        payment_ref = transaction.payee
        if transaction.checknum:
            payment_ref += " " + transaction.checknum
        if transaction.memo:
            payment_ref += " : " + transaction.memo
        
        vals = {
            "date": transaction.date,
            "payment_ref": payment_ref,
            "amount": float(transaction.amount),
            
            "unique_import_id": transaction.id,
        }
        return vals

    @api.model
    def _parse_file(self, data_file):
        try:
            # Leer el contenido del archivo
            content = data_file.decode('utf-8')
            root = ET.fromstring(content)
            
            # Validar si es un archivo de BANDEC
            if root.tag != 'NewDataSet':
                return super()._parse_file(data_file)

            statements = []
            transactions = []
            balance_start = None
            balance_end_real = None
            currency_code = 'CUP'  # Asumimos CUP como la moneda por defecto
            account_number = '0664434001796412'  # Reemplazar con un número de cuenta real

            for element in root.findall("Estado_x0020_de_x0020_Cuenta"):
                observ = element.findtext('observ', '').strip()
                ref = element.findtext('ref_origin', '').strip()
                amount = float(element.findtext('importe', '0.0'))
                date_str = element.findtext('fecha', '').strip()

                # Determinar si es un saldo inicial/final o una transacción
                if observ.startswith("Saldo Contable Anterior"):
                    balance_start = amount
                elif observ.startswith("Saldo Contable Final"):
                    balance_end_real = amount
                elif date_str:
                    # Convertir la cadena de fecha al objeto datetime
                    try:
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
                    except ValueError:
                        raise UserError(_("Formato de fecha no válido en el archivo XML: %s") % date_str)

                    tipo_operacion = element.findtext('tipo', '').strip()
                    signo = -1 if tipo_operacion == 'Db' else 1
                    tipo_extracto = self.identify_bank_statement(observ)

                    # Inicializar variables condicionales
                    acc_num = ""
                    partner_name = ""
                    notes = ""

                    # Destripamos el campo observaciones en función del tipo de extracto
                    if tipo_extracto == 'BPA':
                        acc_num = self.extract_mid_str(observ, "NUM_CUENTA=", "OTR_DATOS=")
                        notes = self.extract_mid_str(observ, "DET_PAGO", "/DET_PAGO")
                    else:
                        partner_name = self.extract_mid_str(observ, "Ordenante:", "Acreditando a:")
                        if not partner_name:
                          partner_name = self.extract_mid_str(observ, "ORDENANTE:", "OBSERVACIONES:")
                        notes = self.extract_mid_str(observ, "Detalles:", "Firma:")

                    # Generar parámetros de búsqueda
                    search_params = {'name': partner_name}
                    if acc_num:  # Solo incluir si acc_num no está vacío
                        search_params['acc_number'] = acc_num

                    # Crear transacción
                    transactions.append({
                        'payment_ref': observ,
                        'date': date_obj,
                        'amount': amount * signo,
                        'partner_id': self.get_partner(search_params),
                        'ref': ref,
                        'narration': f"{partner_name} / {notes} / {acc_num}" if partner_name else notes,
                        'unique_import_id': f"{date_str}-{observ}.....",
                    })

            if not transactions:
                raise UserError(_("El archivo de BANDEC no contiene transacciones válidas."))

            # Modificar el nombre del estado de cuenta para incluir el nombre del archivo importado
            statement_name = f"Estado de Cuenta BANDEC - {transactions[0]['date']}"
            
            statements.append({
                'name': statement_name,
                'date': transactions[0]['date'],
                'balance_start': balance_start,
                'balance_end_real': balance_end_real,
                'transactions': transactions,
            })

            return currency_code, account_number, statements

        except ET.ParseError:
            return super()._parse_file(data_file)
        except Exception as e:
            raise UserError(_("Error al procesar el archivo: %s") % str(e))
