{
    'name': 'Employee Work History',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Кастомна таблиця історії виконань співробітника',
    'depends': ['hr', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/work_history_views.xml',
        'views/hr_employee_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'employee_history_widget/static/src/xml/custom_history_list.xml',
            'employee_history_widget/static/src/js/custom_history_list.js',
        ],
    },
    'installable': True,
    'application': False,
}