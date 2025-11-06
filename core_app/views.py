from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Sum
from django.db.models.functions import TruncWeek, TruncMonth, TruncYear
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from datetime import date

from .models import Expense, Income
from .forms import ExpenseForm, IncomeForm

# ================= PDF GENERATION FUNCTION =================
def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    response = HttpResponse(content_type='application/pdf')
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF <pre>' + html + '</pre>')
    return response

# ================= DASHBOARD =================
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        context['expense_total'] = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        context['income_total'] = incomes.aggregate(Sum('amount'))['amount__sum'] or 0
        context['net_balance'] = context['income_total'] - context['expense_total']

        context['expense_monthly'] = (
            expenses.annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )
        context['income_monthly'] = (
            incomes.annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )

        context['expenses'] = expenses
        context['incomes'] = incomes
        return context

# ================= EXPENSE CRUD =================
class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'add_expense.html'
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def form_valid(self, form):
        expense = form.save(commit=False)
        if expense.date > date.today():
            messages.error(self.request, "Cannot add expense for future dates.")
            return self.form_invalid(form)
        expense.user = self.request.user
        expense.save()
        messages.success(self.request, "Expense added successfully.")
        return super().form_valid(form)


class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'edit_expense.html'
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def form_valid(self, form):
        expense = form.save(commit=False)
        if expense.date > date.today():
            messages.error(self.request, "Cannot set future dates for expenses.")
            return self.form_invalid(form)
        expense.save()
        messages.success(self.request, "Expense updated successfully.")
        return super().form_valid(form)


class ExpenseDeleteView(LoginRequiredMixin, DeleteView):
    model = Expense
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Expense deleted successfully.")
        return super().delete(request, *args, **kwargs)

# ================= INCOME CRUD =================
class IncomeCreateView(LoginRequiredMixin, CreateView):
    model = Income
    form_class = IncomeForm
    template_name = 'add_income.html'
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def form_valid(self, form):
        income = form.save(commit=False)
        if income.date > date.today():
            messages.error(self.request, "Cannot add income for future dates.")
            return self.form_invalid(form)
        income.user = self.request.user
        income.save()
        messages.success(self.request, "Income added successfully.")
        return super().form_valid(form)


class IncomeUpdateView(LoginRequiredMixin, UpdateView):
    model = Income
    form_class = IncomeForm
    template_name = 'edit_income.html'
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def form_valid(self, form):
        income = form.save(commit=False)
        if income.date > date.today():
            messages.error(self.request, "Cannot set future dates for income.")
            return self.form_invalid(form)
        income.save()
        messages.success(self.request, "Income updated successfully.")
        return super().form_valid(form)


class IncomeDeleteView(LoginRequiredMixin, DeleteView):
    model = Income
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Income deleted successfully.")
        return super().delete(request, *args, **kwargs)

# ================= REPORTS =================
class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'reports.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        context['expense_weekly'] = (
            expenses.annotate(week=TruncWeek('date'))
            .values('week')
            .annotate(total=Sum('amount'))
            .order_by('week')
        )
        context['income_weekly'] = (
            incomes.annotate(week=TruncWeek('date'))
            .values('week')
            .annotate(total=Sum('amount'))
            .order_by('week')
        )

        context['expense_monthly'] = (
            expenses.annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )
        context['income_monthly'] = (
            incomes.annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('month')
        )

        context['expense_yearly'] = (
            expenses.annotate(year=TruncYear('date'))
            .values('year')
            .annotate(total=Sum('amount'))
            .order_by('year')
        )
        context['income_yearly'] = (
            incomes.annotate(year=TruncYear('date'))
            .values('year')
            .annotate(total=Sum('amount'))
            .order_by('year')
        )

        context['expense_category'] = (
            expenses.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        return context

# ================= PDF REPORT =================
class ReportsPDFView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        user = request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        # Helper function to combine expenses and incomes by period
        def combine_summary(expenses_qs, incomes_qs, trunc_func):
            expense_summary = (
                expenses_qs.annotate(period=trunc_func('date'))
                .values('period')
                .annotate(total=Sum('amount'))
                .order_by('period')
            )
            income_summary = (
                incomes_qs.annotate(period=trunc_func('date'))
                .values('period')
                .annotate(total=Sum('amount'))
                .order_by('period')
            )
            combined = []
            periods = sorted(set([e['period'] for e in expense_summary] + [i['period'] for i in income_summary]))
            for p in periods:
                expense_total = next((e['total'] for e in expense_summary if e['period'] == p), 0)
                income_total = next((i['total'] for i in income_summary if i['period'] == p), 0)
                combined.append({'period': p, 'expenses': expense_total, 'incomes': income_total})
            return combined

        # Weekly, Monthly, Yearly summaries
        weekly_summary = combine_summary(expenses, incomes, TruncWeek)
        monthly_summary = combine_summary(expenses, incomes, TruncMonth)
        yearly_summary = combine_summary(expenses, incomes, TruncYear)

        # Category-wise expenses
        expense_category = (
            expenses.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        context = {
            'weekly_summary': weekly_summary,
            'monthly_summary': monthly_summary,
            'yearly_summary': yearly_summary,
            'expense_category': expense_category,
        }

        return render_to_pdf('reports_pdf.html', context)