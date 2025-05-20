from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AsiProcess(models.Model):
    _name = "asi.process"
    _description = "Proceso Organizacional"
    _parent_name = "parent_id"
    _parent_store = True
    _rec_name = "name"

    name = fields.Char(required=True)
    description = fields.Text()
    department_id = fields.Many2one("hr.department", string="Departamento")
    responsible_id = fields.Many2one("hr.employee", string="Responsable")
    type = fields.Selection([
        ("horizontal", "Horizontal"),
        ("vertical", "Vertical")
    ], string="Tipo de Proceso", default="horizontal", required=True)
    parent_id = fields.Many2one("asi.process", string="Proceso Padre")
    child_ids = fields.One2many("asi.process", "parent_id", string="Subprocesos")
    task_ids = fields.One2many("project.task", "asi_process_id", string="Tareas")
    parent_path = fields.Char(index=True)

    @api.constrains("parent_id")
    def _check_no_loop(self):
        for rec in self:
            if rec.id and rec.parent_id:
                if rec.id == rec.parent_id.id or rec.id in rec.parent_id._get_ancestor_ids():
                    raise ValidationError("No se permiten lazos cerrados en la jerarquía de procesos.")

    @api.constrains("type", "parent_id")
    def _check_type_constraint(self):
        for rec in self:
            if rec.parent_id:
                if rec.parent_id.type == "horizontal" and rec.type != "horizontal":
                    raise ValidationError("Los subprocesos de un proceso horizontal deben ser también horizontales.")

    def _get_ancestor_ids(self):
        result = set()
        current = self.parent_id
        while current:
            if current.id in result:
                break
            result.add(current.id)
            current = current.parent_id
        return result

    def action_view_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Tareas del Proceso",
            "res_model": "project.task",
            "view_mode": "tree,form",
            "domain": [("asi_process_id", "=", self.id)],
            "context": {"default_asi_process_id": self.id},
        }

