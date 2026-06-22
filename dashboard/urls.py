from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='dashboard_home'),
    path('inventory/', views.inventory_list, name='dashboard_inventory'),
    path('inventory/add/', views.product_create, name='dashboard_product_add'),
    path('inventory/<int:pk>/edit/', views.product_update, name='dashboard_product_edit'),
    path('inventory/<int:pk>/delete/', views.product_delete, name='dashboard_product_delete'),
    path('reports/', views.reports, name='dashboard_reports'),
    path('reports/export/', views.reports_export, name='dashboard_reports_export'),
    path('reports/export/pdf/', views.reports_export_pdf, name='dashboard_reports_export_pdf'),
]
