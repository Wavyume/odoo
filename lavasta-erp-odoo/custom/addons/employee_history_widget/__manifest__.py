{
    'name': 'Employee Work History',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Кастомна таблиця історії виконань співробітника',
    # ДОДАНО 'mrp', бо ми інтегруємось у меню Виробництва
    'depends': ['hr', 'hr_attendance', 'web', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/work_history_views.xml',
        # ДОДАНО файл довідника операцій:
        'views/operation_directory_views.xml', 
        'views/hr_employee_views.xml',
        'views/hr_attendance_views.xml',
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