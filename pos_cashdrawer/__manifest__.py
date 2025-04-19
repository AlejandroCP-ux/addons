# -*- coding: utf-8 -*-
#############################################################################
#
#    Intelligent Cloud Solutions
#
#    Copyright (C) 2024-TODAY Intelligent Cloud Solutions(<https://www.icloud-solutions.net>)
#    Author: Intelligent Cloud Solutions(<https://www.icloud-solutions.net>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    'name': "Open CashDrawer POS",
    'summary': """
        Add Open CashDrawer Button In Point Of Sale. """,
    'description': """
         Open CashDrawer Button In Point Of Sale with a single click. 
    """,
    'author': "Icloud Solutions",
    'website': "https://www.icloud-solutions.net",
    'maintainer': "Icloud Solutions",
    'category': 'Point of Sale',
    'version': '16.0.1.0.0',
    'depends': ['base', 'point_of_sale'],
    'assets': {
        'point_of_sale.assets': [
            'pos_open_cashdrawer/static/src/js/open_drawer.js',
            'pos_open_cashdrawer/static/src/xml/drawer_button.xml',
        ],

    },
    'images': ['static/description/thumbnail.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,

}
