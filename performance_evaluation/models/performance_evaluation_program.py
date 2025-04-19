# -*- coding: utf-8 -*-
import datetime
from odoo import api, fields, models, _
from odoo.fields import Command
from odoo.exceptions import ValidationError, UserError

#Personal Competencies
#Workplace Competencies
#Workplace Competencies
#Technical Competencies
#Other Competencies
#Unsatisfactory
#Needs improvements
#Meet Expectation
#Exceed Expectation
#Outstanding
RATING_VALUATION = {
                    '0':'unsatisfactory',
                    '1':'unsatisfactory',
                    '2':'needs_improvements',
                    '3':'meet_expectation',
                    '4':'exceed_expectation',
                    '5':'outstanding'
}
    
class PerformancePeriod(models.Model):
    _name = "performance.period"
    _description = 'Performance Period'
    
    name = fields.Char(required=True)
    
class PerformanceEvaluationProgramConfig(models.Model):
    _name = 'performance.evaluation.program.config'
    _description = 'Performance Evaluation Program Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name desc"
            
    name = fields.Char(string="Reference", copy=False)
    
    personal_section = fields.Boolean()
    
    
    performance_evaluator = fields.Selection([
                                    ('csuite', 'C-Suite'),
                                    ('manager', 'Manager'),
                                    ('colleague', 'Colleague'),
                                    ('own', 'Own')
                                ])
    email_notify_user_ids = fields.Many2many("res.users", string='Notify Users if New Evaluation Submited and Confirmed')
    
    hr_email_notify = fields.Boolean("Send Email if HR APPROVE or REJECT Evaluation")
    
    company_id = fields.Many2one("res.company", index=True, default=lambda self: self.env.company)
    personal_line_ids = fields.One2many("perosnal.line", "config_id", string="Personal Competencies", copy=True, auto_join=True, tracking=1)
   
class PerosnalLine(models.Model):
    _name = "perosnal.line"
    _description = 'Personal Line'
    
    config_id = fields.Many2one("performance.evaluation.program.config", ondelete='cascade', index=True, copy=False)
    name = fields.Char(string="Description", copy=False)
    min_value = fields.Integer("Lowest Value")
    max_value = fields.Integer("Highest Value")
    
class PerformanceEvaluationProgram(models.Model):
    _name = 'performance.evaluation.program'
    _description = 'Performance Evaluation Program'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name desc"


    @api.onchange('template_id')
    def _onchange_rating(self):
        for rec in self:
            if rec.template_id:
                rec.personal_ev_line_ids = False
                for pl in rec.template_id.personal_line_ids:
                    pline = {
                                'name':pl.name,
                                'evaluation':pl.max_value
                             }
                    rec.personal_ev_line_ids = [(0,0,pline)]
            else:
                rec.personal_ev_line_ids = False
               
            rec.evaluator_relationship = rec.template_id.performance_evaluator

            if rec.template_id.performance_evaluator =='manager':
                rec.evaluator_employee_id = rec.employee_id.parent_id
            elif rec.template_id.performance_evaluator =='own':
                rec.evaluator_employee_id = rec.employee_id
            else:
                rec.evaluator_employee_id = False

    @api.onchange('evaluator_employee_id')
    def _compute_evaluator_emp_info(self):
        for rec in self:
            rec.evaluator_department_id = rec.evaluator_employee_id.department_id
            rec.evaluator_job_id = rec.evaluator_employee_id.job_id
            if rec.evaluator_employee_id:
                if rec.evaluator_department_id.id == rec.department_id.id:
                    rec.evaluator_department_relationship = 'intra'
                else:
                    rec.evaluator_department_relationship = 'inter'
            else:
                rec.evaluator_department_relationship = False            
            
    @api.depends('employee_id')
    def _compute_emp_info(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id
            rec.job_id = rec.employee_id.job_id
            rec.manager_id = rec.employee_id.parent_id
            rec.birthday = rec.employee_id.birthday
            rec.country_id = rec.employee_id.country_id
            rec.image_1920 = rec.employee_id.image_1920
            rec.visa_expire = rec.employee_id.visa_expire
            if rec.employee_id.default_evaluation_template_id: 
                rec.template_id= rec.employee_id.default_evaluation_template_id
            #rec.performance_period_id = False
    
    @api.depends('overall_personal_score')
    def _compute_overall(self):
        for rec in self:
            
            rec.overall_score = 0.00
            overall_score = 0.00
            len_av = 0
            if rec.template_id.personal_section:
                len_av += 1
                overall_score += rec.overall_personal_score
                        
            if len_av >0:
                rec.overall_score =  float(format(overall_score/len_av, '.2f'))
            else:
                rec.overall_score =  float(format(overall_score/1, '.2f'))

            
            

    @api.depends('personal_ev_line_ids.evaluation')
    def _compute_personal_ev(self):
        for rec in self:
            rec.overall_personal_score = 0.00
            len_ev = len(rec.personal_ev_line_ids) or 1
            t_rating = 0.00
            for line in rec.personal_ev_line_ids:
                t_rating += int(line.evaluation)
            rec.overall_personal_score = t_rating
   

    name = fields.Char(string="Reference", copy=False, default=lambda self: _('New'))
    template_id = fields.Many2one("performance.evaluation.program.config", tracking=1)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Completed'),
        ('reject', 'Rejected')
        ], string='Status', copy=False, tracking=1, default='draft')
    
    note = fields.Char(string="Remark", copy=False)
    
    personal_ev_line_ids = fields.One2many("program.perosnal.line", "program_id", string="Personal Competencies", copy=True, auto_join=True, tracking=1)

    active = fields.Boolean(default=True, tracking=1)
    company_id = fields.Many2one("res.company", index=True, default=lambda self: self.env.company)
    performance_period_id = fields.Many2one("performance.period")
    
    employee_id = fields.Many2one("hr.employee", tracking=1, copy=False)
    department_id = fields.Many2one("hr.department", compute="_compute_emp_info", store=True)
    job_id = fields.Many2one("hr.job", compute="_compute_emp_info", store=True)
    
    
    evaluator_employee_id = fields.Many2one("hr.employee", tracking=1, copy=False)
    evaluator_department_id = fields.Many2one("hr.department", compute="_compute_evaluator_emp_info", store=True)
    evaluator_job_id = fields.Many2one("hr.job", compute="_compute_evaluator_emp_info", store=True)
    
    evaluator_department_relationship = fields.Selection([
                                                ('intra', 'Intra Department'),
                                                ('inter', 'Inter Department'),
                                            ], compute="_compute_evaluator_emp_info", store=True)
    evaluator_relationship = fields.Selection([
                                                ('csuite', 'C-Suite'),
                                                ('manager', 'Manager'),
                                                ('colleague', 'Colleague'),
                                                ('own', 'OWN')
                                            ])
    
    manager_id = fields.Many2one("hr.employee", compute="_compute_emp_info", store=True)
    visa_expire = fields.Date('Visa Expire Date', compute="_compute_emp_info", store=True)
        
    image_1920 = fields.Image(compute="_compute_emp_info", store=True)
    country_id = fields.Many2one(
        'res.country', 'Nationality (Country)', compute="_compute_emp_info", store=True)
    birthday = fields.Date('Date of Birth', compute="_compute_emp_info", store=True)
    date_of_joining = fields.Date(copy=False)
    length_of_service = fields.Char(copy=False)
    location = fields.Char(copy=False)
    job_category = fields.Char(copy=False)
    
    disciplinary_action = fields.Char(copy=False)
    nature_of_disclipinary_action = fields.Char(copy=False)
    annual_leave_balance = fields.Char(copy=False)
    annual_leave_consumed_this_year = fields.Char(copy=False)
    visa_days_to_expire = fields.Char(copy=False)
    labor_card_expiry = fields.Date(copy=False)
    labor_card_days_to_expire = fields.Char(copy=False)
    
    job_description = fields.Text(copy=False)
    hr_remarks = fields.Text(copy=False)
    manager_remarks = fields.Text(copy=False)
    positive_points = fields.Text(tracking=1, copy=False)
    negative_points = fields.Text(tracking=1, copy=False)
    extra_remarks = fields.Text(tracking=1, copy=False)
    

    date_of_evaluation = fields.Datetime(copy=False)
    
    overall_score = fields.Float(compute="_compute_overall", store=True, tracking=1)
            
    overall_personal_score = fields.Float(compute="_compute_personal_ev", store=True)
        


    #Human Resource Remarks for renewal of labor contract
    #Line Manager Remarks for renewal of labor contract



    @api.model
    def create(self, vals):
        if 'company_id' in vals:
            self = self.with_company(vals['company_id'])
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('performance.evaluation.program') or _('New')
        if 'employee_id' in vals and 'template_id' in vals:
            performance_evaluator = self.env['performance.evaluation.program.config'].sudo().browse(vals['template_id']).performance_evaluator
            if performance_evaluator =='manager':
                vals['evaluator_employee_id'] = self.env['hr.employee'].sudo().browse(vals['employee_id']).parent_id.id
            elif performance_evaluator =='own':
                vals['evaluator_employee_id'] = vals['employee_id']
        result = super(PerformanceEvaluationProgram, self).create(vals)
        return result
    
    
    def write(self, vals):
    
        if 'template_id' in vals:
            performance_evaluator = self.env['performance.evaluation.program.config'].sudo().browse(vals['template_id']).performance_evaluator
            if performance_evaluator =='manager':
                vals['evaluator_employee_id'] = self.employee_id.parent_id.id
            elif performance_evaluator =='own':
                vals['evaluator_employee_id'] = self.employee_id.id

        res = super(PerformanceEvaluationProgram, self).write(vals)
        return res
        
    def confirm_program(self):
        for rec in self:
            web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            link = web_base_url + '/web#id=%d&view_type=form&model=%s' % (rec.id, rec._name)
            mail_content = "  Hello  " + \
                    ",<br>New Employee Evaluation Request " + rec.name + ", is added in the system." + \
                    "<br><b>For Employee - </b>" + str(rec.employee_id.name) +\
                    "<br>"+\
                    "<p style='box-sizing:border-box;margin-bottom: 0px;'>" +\
                    "To access Evaluation Request, you can use the following link: </p>" +\
                    "<p style='margin:0px 0 12px 0;box-sizing:border-box;'></p>" +\
                    "<div style='margin: 16px 0px 16px 0px;'>" +\
                    "<a href="+link+ " style='padding: 5px 10px; color: #FFFFFF;"+\
                    "background-color: #875A7B;"+\
                    "border: 1px solid #875A7B;"+\
                    "border-radius: 3px'>"+\
                    "<strong style='box-sizing:border-box;font-weight:bolder;'>View Evaluation Request</strong>" +\
                    "</a>"+\
                    "</div>" +\
                    "<br><br>Thank You, <br>" + str(rec.company_id.name)
        
            main_content = {
                'subject': _('New Employee Evaluation Request - %s for Employee %s') % (rec.name,rec.employee_id.name),
                'author_id': rec.env.user.partner_id.id,
                'body_html': mail_content,
                'email_to': rec.evaluator_employee_id.user_id.login,
                'recipient_ids': [(6,0,[user.partner_id.id for user in rec.template_id.email_notify_user_ids])],
            }
            self.env['mail.mail'].create(main_content).sudo().send()
            
            rec.state = 'done'
    
    def approve_hr_program(self):
        for rec in self:
            if rec.template_id.hr_email_notify:
                web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                link = web_base_url + '/web#id=%d&view_type=form&model=%s' % (rec.id, rec._name)
                mail_content = "  Hello  " + \
                        ",<br>Employee Evaluation Request " + rec.name + ", is Completed in the system." + \
                        "<br><b>For Employee - </b>" + str(rec.employee_id.name) +\
                        "<br>"+\
                        "<b>Evaluator Employee - </b>" + str(rec.evaluator_employee_id.name) +\
                        "<br>"+\
                        "<p style='box-sizing:border-box;margin-bottom: 0px;'>" +\
                        "To access Evaluation, you can use the following link: </p>" +\
                        "<p style='margin:0px 0 12px 0;box-sizing:border-box;'></p>" +\
                        "<div style='margin: 16px 0px 16px 0px;'>" +\
                        "<a href="+link+ " style='padding: 5px 10px; color: #FFFFFF;"+\
                        "background-color: #875A7B;"+\
                        "border: 1px solid #875A7B;"+\
                        "border-radius: 3px'>"+\
                        "<strong style='box-sizing:border-box;font-weight:bolder;'>View Evaluation Request</strong>" +\
                        "</a>"+\
                        "</div>" +\
                        "<br><br>Thank You, <br>" + str(rec.company_id.name)
            
                main_content = {
                    'subject': _('HR Evaluation Completed - %s for Employee %s') % (rec.name,rec.employee_id.name),
                    'author_id': rec.env.user.partner_id.id,
                    'body_html': mail_content,
                    'email_to': rec.evaluator_employee_id.user_id.login,
                    'recipient_ids': [(6,0,[user.partner_id.id for user in rec.template_id.email_notify_user_ids])],
                }
                self.env['mail.mail'].sudo().create(main_content).send()
            
            rec.state = 'done'

    def reject_hr_program(self):
        for rec in self:
            if rec.template_id.hr_email_notify:
                web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                link = web_base_url + '/web#id=%d&view_type=form&model=%s' % (rec.id, rec._name)
                mail_content = "  Hello  " + \
                        ",<br>Employee Evaluation Request " + rec.name + ", is Rejected by HR." + \
                        "<br><b>For Employee - </b>" + str(rec.employee_id.name) +\
                        "<br>"+\
                        "<b>Evaluator Employee - </b>" + str(rec.evaluator_employee_id.name) +\
                        "<br>"+\
                        "<p style='box-sizing:border-box;margin-bottom: 0px;'>" +\
                        "To access Evaluation, you can use the following link: </p>" +\
                        "<p style='margin:0px 0 12px 0;box-sizing:border-box;'></p>" +\
                        "<div style='margin: 16px 0px 16px 0px;'>" +\
                        "<a href="+link+ " style='padding: 5px 10px; color: #FFFFFF;"+\
                        "background-color: #875A7B;"+\
                        "border: 1px solid #875A7B;"+\
                        "border-radius: 3px'>"+\
                        "<strong style='box-sizing:border-box;font-weight:bolder;'>View Evaluation Request</strong>" +\
                        "</a>"+\
                        "</div>" +\
                        "<br><br>Thank You, <br>" + str(rec.company_id.name)
            
                main_content = {
                    'subject': _('HR Evaluation Rejected - %s for Employee %s') % (rec.name,rec.employee_id.name),
                    'author_id': rec.env.user.partner_id.id,
                    'body_html': mail_content,
                    'email_to': rec.evaluator_employee_id.user_id.login,
                    'recipient_ids': [(6,0,[user.partner_id.id for user in rec.template_id.email_notify_user_ids])],
                }
                self.env['mail.mail'].sudo().create(main_content).send()
            rec.state = 'reject'
                                 
    def reset_to_draft_program(self):
        for rec in self:
            rec.state = 'draft'


    def send_reminder_email(self):
        for rec in self:
            web_base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            link = web_base_url + '/web#id=%d&view_type=form&model=%s' % (rec.id, rec._name)
            mail_content = "  Hello  " + \
                    ",<br>Employee Evaluation Request " + rec.name + ", is pending in the system." + \
                    "<br><b>For Employee - </b>" + str(rec.employee_id.name) +\
                    "<br>"+\
                    "<b>Evaluator Employee - </b>" + str(rec.evaluator_employee_id.name) +\
                    "<br>"+\
                    "<b>Kindly Submit evaluation as early as possible. </b>" + \
                    "<br>"+\
                    "<p style='box-sizing:border-box;margin-bottom: 0px;'>" +\
                    "To access Evaluation Request, you can use the following link: </p>" +\
                    "<p style='margin:0px 0 12px 0;box-sizing:border-box;'></p>" +\
                    "<div style='margin: 16px 0px 16px 0px;'>" +\
                    "<a href="+link+ " style='padding: 5px 10px; color: #FFFFFF;"+\
                    "background-color: #875A7B;"+\
                    "border: 1px solid #875A7B;"+\
                    "border-radius: 3px'>"+\
                    "<strong style='box-sizing:border-box;font-weight:bolder;'>View Evaluation Request</strong>" +\
                    "</a>"+\
                    "</div>" +\
                    "<br><br>Thank You, <br>" + str(rec.company_id.name)
        
            main_content = {
                'subject': _('Reminder for Employee Evaluation - %s for Employee %s') % (rec.name,rec.employee_id.name),
                'author_id': rec.env.user.partner_id.id,
                'body_html': mail_content,
                'email_to': rec.evaluator_employee_id.user_id.login,
                'recipient_ids': [(6,0,[user.partner_id.id for user in rec.template_id.email_notify_user_ids])],
            }
            self.env['mail.mail'].sudo().create(main_content).send()
            
            

    def open_all_evaluations(self):
        self.ensure_one()
        records = self.env['performance.evaluation.program'].search([('employee_id', '=', self.employee_id.id)])
        action = self.env["ir.actions.actions"]._for_xml_id("performance_evaluation.performance_evaluation_program_action")
        action["context"] = {
            "create": False,
        }
        if len(records) > 1:
            action['domain'] = [('id', 'in', records.ids)]
        elif len(records) == 1:
            form_view = [(self.env.ref('performance_evaluation.performance_evaluation_program_view_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = records.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.model
    def createdefaults_etm(self):
        employees = self.env['hr.employee'].search([])
        currentperiod = fields.Date.today().strftime("%Y-%m")
        period = self.env['performance.period'].search([('name', '=', currentperiod)])
        if not period:
            period = self.env['performance.period'].create({'name': currentperiod})
        
        for employee in employees:
            if employee.default_evaluation_template_id:
                this_personal_lines = []
                for pl in employee.default_evaluation_template_id.personal_line_ids:
                    pline = {
                                'name':pl.name,
                                'evaluation':pl.max_value
                             }
                    this_personal_lines.append(Command.create(pline))
                        
                res = self.env['performance.evaluation.program'].create({
                  'employee_id': employee.id,
                  'performance_period_id' : period.id,           
                  'template_id': employee.default_evaluation_template_id.id,
                  'personal_ev_line_ids' : this_personal_lines
            })
        return True        
        
class ProgramPerosnalLine(models.Model):
    _name = "program.perosnal.line"
    _description = 'Program Perosnal Line'

    @api.onchange('evaluation')
    def _onchange_rating(self):
        for rec in self:
            if not rec.program_id.template_id.performance_evaluator =='own' and rec.program_id.evaluator_employee_id.user_id.id != rec.env.user.id and not rec.env.user.has_group ('performance_evaluation.group_performance_evaluation_admin'):
                raise ValidationError("You are not authorize to Submit Current Evaluation!")
            
    program_id = fields.Many2one("performance.evaluation.program", ondelete='cascade', index=True)
    state = fields.Selection(related="program_id.state")
    name = fields.Char(string="Description")
    evaluation = fields.Integer("Evaluation")
    
        
 
