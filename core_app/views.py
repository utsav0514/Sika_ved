import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import json
from datetime import date

from django.shortcuts import redirect
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
from django.core.serializers.json import DjangoJSONEncoder

from .models import Expense, Income
from .forms import ExpenseForm, IncomeForm


# ================= PDF RENDERER CLASS =================
class PDFRenderer:
    def __init__(self, template_src, context_dict=None, filename="report.pdf"):
        self.template_src = template_src
        self.context_dict = context_dict or {}
        self.filename = filename

    def render(self):
        template = get_template(self.template_src)
        html = template.render(self.context_dict)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{self.filename}"'
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('Error generating PDF <pre>' + html + '</pre>')
        return response


# ================= CHART GENERATOR CLASS =================
class ChartGenerator:
    def __init__(self, title='Chart', kind='bar', figsize=(6, 4)):
        self.title = title
        self.kind = kind
        self.figsize = figsize

    def plot(self, x, y):
        fig, ax = plt.subplots(figsize=self.figsize)
        if self.kind == 'bar':
            ax.bar(x, y, color='skyblue')
        elif self.kind == 'line':
            ax.plot(x, y, marker='o', color='green')
        elif self.kind == 'pie':
            ax.pie(y, labels=x, autopct='%1.1f%%')
        ax.set_title(self.title)
        plt.xticks(rotation=45)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"


# ================= PERIOD LABEL UTILITIES =================
def get_week_label(date_obj):
    """Convert a date to 'YYYY-MM-First/Second/Third/Fourth Week' format."""
    month = date_obj.month
    year = date_obj.year
    day = date_obj.day
    first_day_of_month = date_obj.replace(day=1)
    week_of_month = (day + first_day_of_month.weekday() - 1) // 7 + 1
    week_names = ["First Week", "Second Week", "Third Week", "Fourth Week", "Fifth Week"]
    return f"{year}-{month:02d}-{week_names[week_of_month-1]}"


# ================= REPORTS HELPER =================
class ReportsHelper:
    @staticmethod
    def combine_summary(exp_qs, inc_qs, trunc_func, period_type='week'):
        """Combine expense and income summaries based on truncation."""
        expense_summary = (
            exp_qs.annotate(period=trunc_func('date'))
            .values('period')
            .annotate(total=Sum('amount'))
            .order_by('period')
        )
        income_summary = (
            inc_qs.annotate(period=trunc_func('date'))
            .values('period')
            .annotate(total=Sum('amount'))
            .order_by('period')
        )

        combined = []
        periods = sorted(set([e['period'] for e in expense_summary] + [i['period'] for i in income_summary]))

        for p in periods:
            if period_type == 'week':
                label = get_week_label(p)
            elif period_type == 'month':
                label = p.strftime('%Y-%m')
            elif period_type == 'year':
                label = p.strftime('%Y')
            else:
                label = p.strftime('%Y-%m-%d')

            combined.append({
                'period': label,
                'expenses': next((e['total'] for e in expense_summary if e['period'] == p), 0),
                'incomes': next((i['total'] for i in income_summary if i['period'] == p), 0),
            })
        return combined


# ================= DASHBOARD =================
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        expenses = Expense.objects.filter(user=user).order_by('-date')
        incomes = Income.objects.filter(user=user).order_by('-date')

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

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        messages.success(request, "Income deleted successfully.")
        return redirect(self.success_url)


# ================= REPORTS =================
# ================= REPORTS =================
class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'reports.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        # ================= SUMMARY TABLES ===================
        context['weekly_summary'] = ReportsHelper.combine_summary(
            expenses, incomes, TruncWeek, period_type='week'
        )
        context['monthly_summary'] = ReportsHelper.combine_summary(
            expenses, incomes, TruncMonth, period_type='month'
        )
        context['yearly_summary'] = ReportsHelper.combine_summary(
            expenses, incomes, TruncYear, period_type='year'
        )

        # ================= CATEGORY ===================
        # Total category summary for table
        expense_category = (
            expenses.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        # Month-wise category totals for pie chart
        expense_category_by_month = list(
            expenses.annotate(month=TruncMonth('date'))
            .values('month', 'category__name')
            .annotate(total=Sum('amount'))
            .order_by('-month', '-total')
        )

        context['expense_category'] = expense_category  # For table
        context['expense_category_json'] = json.dumps(expense_category_by_month, cls=DjangoJSONEncoder)  # For chart

        # ================= JSON FOR OTHER CHARTS ===================
        context['weekly_summary_json'] = json.dumps(context['weekly_summary'], cls=DjangoJSONEncoder)
        context['monthly_summary_json'] = json.dumps(context['monthly_summary'], cls=DjangoJSONEncoder)
        context['yearly_summary_json'] = json.dumps(context['yearly_summary'], cls=DjangoJSONEncoder)

        return context



# ================= PDF REPORT =================
class ReportsPDFView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        user = request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        weekly_summary = ReportsHelper.combine_summary(expenses, incomes, TruncWeek, period_type='week')
        monthly_summary = ReportsHelper.combine_summary(expenses, incomes, TruncMonth, period_type='month')
        yearly_summary = ReportsHelper.combine_summary(expenses, incomes, TruncYear, period_type='year')

        expense_category = (
            expenses.values('category__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        # Charts
        weekly_chart = ChartGenerator('Weekly Expenses', 'bar').plot(
            [w['period'] for w in weekly_summary],
            [w['expenses'] for w in weekly_summary]
        )
        monthly_chart = ChartGenerator('Monthly Expenses', 'line').plot(
            [m['period'] for m in monthly_summary],
            [m['expenses'] for m in monthly_summary]
        )
        yearly_chart = ChartGenerator('Yearly Expenses', 'bar').plot(
            [y['period'] for y in yearly_summary],
            [y['expenses'] for y in yearly_summary]
        )
        category_chart = ChartGenerator('Expenses by Category', 'pie').plot(
            [c['category__name'] for c in expense_category],
            [c['total'] for c in expense_category]
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

        return PDFRenderer('reports_pdf.html', context).render()
