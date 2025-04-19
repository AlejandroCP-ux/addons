# pylint: disable=pointless-statement
{
    'name': "Fix Google Fonts",
    'summary': """Removes Google Fonts from calls""",
    'author': "Bytist GmbH",
    'website': "https://bytist.de",
    'category': 'Website',
    'version': '16.0.1.0.1',
    'depends': ['web', 'website'],
    'license': 'OPL-1',
    'support': 'contact@bytist.de',
    'uninstall_hook': 'uninstall_hook',
    'post_init_hook': 'post_init_hook',
    'data': [
        'views/website_templates.xml'
    ],
    'images': [
        'static/description/banner.png'
    ]
}
