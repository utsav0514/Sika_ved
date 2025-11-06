from django.urls import path
from .views import (
    DashboardView,
    ExpenseCreateView, ExpenseUpdateView, ExpenseDeleteView,
    IncomeCreateView, IncomeUpdateView, IncomeDeleteView,
    ReportsView, ReportsPDFView
)

urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),

    # Expense routes
    path('expense/add/', ExpenseCreateView.as_view(), name='add_expense'),
    path('expense/edit/<int:pk>/', ExpenseUpdateView.as_view(), name='edit_expense'),
    path('expense/delete/<int:pk>/', ExpenseDeleteView.as_view(), name='delete_expense'),

    # Income routes
    path('income/add/', IncomeCreateView.as_view(), name='add_income'),
    path('income/edit/<int:pk>/', IncomeUpdateView.as_view(), name='edit_income'),
    path('income/delete/<int:pk>/', IncomeDeleteView.as_view(), name='delete_income'),

    # Reports
    path('reports/', ReportsView.as_view(), name='reports'),
    path('reports/pdf/', ReportsPDFView.as_view(), name='reports_pdf'),
]
