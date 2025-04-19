# -*- coding: utf-8 -*-

def migrate(cr, version):
    # Verificar si las columnas ya existen para evitar errores
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_company' 
        AND column_name='workplan_planner_partner_id'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN workplan_planner_partner_id integer REFERENCES res_partner(id)
        """)

    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_company' 
        AND column_name='workplan_approver_partner_id'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN workplan_approver_partner_id integer REFERENCES res_partner(id)
        """)