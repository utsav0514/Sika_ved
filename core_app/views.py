import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
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
import io
import base64
from django.core.serializers.json import DjangoJSONEncoder
import json


# ================= PDF GENERATION FUNCTION =================
def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF <pre>' + html + '</pre>')
    return response

# ================= HELPER: Matplotlib chart to Base64 =================
def plot_to_base64(x, y, title='Chart', kind='bar'):
    fig, ax = plt.subplots(figsize=(6, 4))
    if kind == 'bar':
        ax.bar(x, y, color='skyblue')
    elif kind == 'line':
        ax.plot(x, y, marker='o', color='green')
    elif kind == 'pie':
        ax.pie(y, labels=x, autopct='%1.1f%%')
    ax.set_title(title)
    plt.xticks(rotation=45)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"

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

    # Completely override GET to delete immediately
    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        messages.success(request, "Expense deleted successfully.")
        return redirect(self.success_url)


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

    # Completely override GET to delete immediately
    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        messages.success(request, "Income deleted successfully.")
        return redirect(self.success_url)
# ================= REPORTS =================
class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'reports.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

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
                combined.append({'period': p.strftime('%Y-%m-%d'), 'expenses': expense_total, 'incomes': income_total})
            return combined

        weekly_summary = combine_summary(expenses, incomes, TruncWeek)
        monthly_summary = combine_summary(expenses, incomes, TruncMonth)
        yearly_summary = combine_summary(expenses, incomes, TruncYear)

        expense_category = list(
            expenses.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        # Pass **raw Python objects** for tables
        context['weekly_summary'] = weekly_summary
        context['monthly_summary'] = monthly_summary
        context['yearly_summary'] = yearly_summary
        context['expense_category'] = expense_category

        # Pass JSON for JavaScript charts
        context['weekly_summary_json'] = json.dumps(weekly_summary, cls=DjangoJSONEncoder)
        context['monthly_summary_json'] = json.dumps(monthly_summary, cls=DjangoJSONEncoder)
        context['yearly_summary_json'] = json.dumps(yearly_summary, cls=DjangoJSONEncoder)
        context['expense_category_json'] = json.dumps(expense_category, cls=DjangoJSONEncoder)

        return context
# ================= PDF REPORT =================
class ReportsPDFView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        user = request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

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

        weekly_summary = combine_summary(expenses, incomes, TruncWeek)
        monthly_summary = combine_summary(expenses, incomes, TruncMonth)
        yearly_summary = combine_summary(expenses, incomes, TruncYear)
        expense_category = (
            expenses.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        # Generate charts as images
        weekly_chart = plot_to_base64(
            [w['period'].strftime('%d %b') for w in weekly_summary],
            [w['expenses'] for w in weekly_summary],
            'Weekly Expenses', kind='bar'
        )

        monthly_chart = plot_to_base64(
            [m['period'].strftime('%b %Y') for m in monthly_summary],
            [m['expenses'] for m in monthly_summary],
            'Monthly Expenses', kind='line'
        )

        yearly_chart = plot_to_base64(
            [y['period'].strftime('%Y') for y in yearly_summary],
            [y['expenses'] for y in yearly_summary],
            'Yearly Expenses', kind='bar'
        )

        category_chart = plot_to_base64(
            [c['category__name'] for c in expense_category],
            [c['total'] for c in expense_category],
            'Expenses by Category', kind='pie'
        )

        context = {
            'weekly_summary': weekly_summary,
            'monthly_summary': monthly_summary,
            'yearly_summary': yearly_summary,
            'expense_category': expense_category,
            'weekly_chart': weekly_chart,
            'monthly_chart': monthly_chart,
            'yearly_chart': yearly_chart,
            'category_chart': category_chart,
        }

        return render_to_pdf('reports_pdf.html', context)