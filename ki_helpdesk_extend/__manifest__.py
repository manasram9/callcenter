# -*- coding: utf-8 -*-


{
    'name': "Helpdesk Ticket Extend",
    'summary': """Helpdesk Ticket Extend""",
    'description': """Helpdesk Ticket Extend""",
    'version': "0.2",
    'category': "CRM",
    'author': "Manas Ram Satapathy",
    "depends": [
        'website_helpdesk_form', 'helpdesk', 'website_form'
    ],
    "data": [
        'security/security.xml',
        'views/helpdesk_ticket_view.xml',
        'views/res_users_view.xml',
        'views/portal_template.xml',
        'views/assets.xml'
    ],
    'application': False,
    'installable': True,
}
