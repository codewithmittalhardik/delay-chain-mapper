from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Pages
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_page_view, name='login_page'),

    # Project Data
    path('api/project/', views.get_project, name='get_project'),
    path('api/project/save/', views.save_project, name='save_project'),

    # Task CRUD
    path('api/task/create/', views.create_task, name='create_task'),
    path('api/task/<str:task_id>/delete/', views.delete_task, name='delete_task'),

    # Delay Propagation
    path('api/delay/propagate/', views.propagate_delay, name='propagate_delay'),

    # AI (Groq)
    path('api/generate-chain/', views.generate_chain_view, name='generate_chain'),
    path('api/analyze-delay/', views.analyze_delay_view, name='analyze_delay'),

    # PDF Export
    path('api/export-pdf/', views.export_pdf, name='export_pdf'),

    # Auth
    path('api/auth/login/', views.login_view, name='login'),
    path('api/auth/logout/', views.logout_view, name='logout'),
    path('api/auth/status/', views.status_view, name='status'),
    path('api/auth/register/', views.register_api_view, name='register_api'),
    path('register/', views.register_page_view, name='register_page'),

    # Admin Analytics
    path('api/admin/analytics/', views.admin_analytics, name='admin_analytics'),
]
