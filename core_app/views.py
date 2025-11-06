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


# ================= PDF RENDERER =================
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


# ================= CHART GENERATOR =================
class ChartGenerator:
    def __init__(self, title='Chart', kind='bar', figsize=(6, 4)):
        self.title = title
        self.kind = kind
        self.figsize = figsize

    def plot(self, labels, datasets):
        fig, ax = plt.subplots(figsize=self.figsize)

        if self.kind == 'bar':
            width = 0.35
            x = range(len(labels))
            for i, dataset in enumerate(datasets):
                ax.bar([p + i*width for p in x], dataset['data'], width=width,
                       label=dataset['label'], color=dataset['color'])
            ax.set_xticks([p + width/2 for p in x])
            ax.set_xticklabels(labels, rotation=45)

        elif self.kind == 'line':
            for dataset in datasets:
                ax.plot(labels, dataset['data'], marker='o',
                        label=dataset['label'], color=dataset['color'])

        elif self.kind == 'pie':
            dataset = datasets[0]
            ax.pie(dataset['data'], labels=labels, autopct='%1.1f%%', colors=dataset.get('colors'))

        ax.set_title(self.title)
        ax.legend()
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"


# ================= UTILITIES =================
def get_week_label(date_obj):
    month = date_obj.month
    year = date_obj.year
    day = date_obj.day
    first_day_of_month = date_obj.replace(day=1)
    week_of_month = (day + first_day_of_month.weekday() - 1) // 7 + 1
    week_names = ["First Week", "Second Week", "Third Week", "Fourth Week", "Fifth Week"]
    return f"{year}-{month:02d}-{week_names[week_of_month-1]}"


class ReportsHelper:
    @staticmethod
    def combine_summary(exp_qs, inc_qs, trunc_func, period_type='week'):
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
        periods = sorted(set([e['period'] for e in expense_summary] +
                             [i['period'] for i in income_summary]))

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

        total_expense = Expense.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or 0
        total_income = Income.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or 0

        remaining_money = total_income - total_expense

        context.update({
            'expense_total': total_expense,
            'income_total': remaining_money,
            'net_balance': remaining_money,
            'expenses': Expense.objects.filter(user=user).order_by('-date')[:5],
            'incomes': Income.objects.filter(user=user).order_by('-date')[:5],
            'expense_monthly': (
                Expense.objects.filter(user=user)
                       .annotate(month=TruncMonth('date'))
                       .values('month')
                       .annotate(total=Sum('amount'))
                       .order_by('month')
            ),
            'income_monthly': (
                Income.objects.filter(user=user)
                      .annotate(month=TruncMonth('date'))
                      .values('month')
                      .annotate(total=Sum('amount'))
                      .order_by('month')
            ),
        })
        return context


# ================= EXPENSE CBVs =================
class ExpenseBaseMixin(LoginRequiredMixin):
    model = Expense
    form_class = ExpenseForm
    login_url = '/login/'

    def form_valid(self, form):
        obj = form.save(commit=False)
        if obj.date > date.today():
            messages.error(self.request, "Cannot set future dates.")
            return self.form_invalid(form)
        obj.user = self.request.user
        obj.save()
        messages.success(self.request, f"{self.model.__name__} saved successfully.")
        return super().form_valid(form)


class ExpenseCreateView(ExpenseBaseMixin, CreateView):
    template_name = 'add_expense.html'
    success_url = reverse_lazy('dashboard')


class ExpenseUpdateView(ExpenseBaseMixin, UpdateView):
    template_name = 'edit_expense.html'
    success_url = reverse_lazy('dashboard')


class ExpenseDeleteView(LoginRequiredMixin, DeleteView):
    model = Expense
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        messages.success(request, "Expense deleted successfully.")
        return redirect(self.success_url)


# ================= INCOME CBVs =================
class IncomeBaseMixin(LoginRequiredMixin):
    model = Income
    form_class = IncomeForm
    login_url = '/login/'

    def form_valid(self, form):
        obj = form.save(commit=False)
        if obj.date > date.today():
            messages.error(self.request, "Cannot set future dates.")
            return self.form_invalid(form)
        obj.user = self.request.user
        obj.save()
        messages.success(self.request, f"{self.model.__name__} saved successfully.")
        return super().form_valid(form)


class IncomeCreateView(IncomeBaseMixin, CreateView):
    template_name = 'add_income.html'
    success_url = reverse_lazy('dashboard')


class IncomeUpdateView(IncomeBaseMixin, UpdateView):
    template_name = 'edit_income.html'
    success_url = reverse_lazy('dashboard')


class IncomeDeleteView(LoginRequiredMixin, DeleteView):
    model = Income
    success_url = reverse_lazy('dashboard')
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.delete()
        messages.success(request, "Income deleted successfully.")
        return redirect(self.success_url)


# ================= REPORTS CBV =================
class ReportsView(LoginRequiredMixin, TemplateView):
    template_name = 'reports.html'
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        context['weekly_summary'] = ReportsHelper.combine_summary(expenses, incomes, TruncWeek, 'week')
        context['monthly_summary'] = ReportsHelper.combine_summary(expenses, incomes, TruncMonth, 'month')
        context['yearly_summary'] = ReportsHelper.combine_summary(expenses, incomes, TruncYear, 'year')

        expense_category = (
            expenses.values('category__name')
                    .annotate(total=Sum('amount'))
                    .order_by('-total')
        )

        context['expense_category'] = expense_category
        context['expense_category_json'] = json.dumps(
            list(expenses.annotate(month=TruncMonth('date'))
                       .values('month', 'category__name')
                       .annotate(total=Sum('amount'))
                       .order_by('-month', '-total')),
            cls=DjangoJSONEncoder
        )

        # JSON for charts
        context['weekly_summary_json'] = json.dumps(context['weekly_summary'], cls=DjangoJSONEncoder)
        context['monthly_summary_json'] = json.dumps(context['monthly_summary'], cls=DjangoJSONEncoder)
        context['yearly_summary_json'] = json.dumps(context['yearly_summary'], cls=DjangoJSONEncoder)

        return context


# ================= PDF REPORT CBV =================
class ReportsPDFView(LoginRequiredMixin, View):
    login_url = '/login/'

    def get(self, request, *args, **kwargs):
        user = request.user
        expenses = Expense.objects.filter(user=user)
        incomes = Income.objects.filter(user=user)

        weekly_summary = ReportsHelper.combine_summary(expenses, incomes, TruncWeek, 'week')
        monthly_summary = ReportsHelper.combine_summary(expenses, incomes, TruncMonth, 'month')
        yearly_summary = ReportsHelper.combine_summary(expenses, incomes, TruncYear, 'year')

        expense_category = (
            expenses.values('category__name')
                    .annotate(total=Sum('amount'))
                    .order_by('-total')
        )

        weekly_chart = ChartGenerator('Weekly Income vs Expense', 'bar').plot(
            [w['period'] for w in weekly_summary],
            [
                {'label':'Expenses', 'data':[w['expenses'] for w in weekly_summary], 'color':'red'},
                {'label':'Incomes', 'data':[w['incomes'] for w in weekly_summary], 'color':'green'}
            ]
        )

        monthly_chart = ChartGenerator('Monthly Income vs Expense', 'line').plot(
            [m['period'] for m in monthly_summary],
            [
                {'label':'Expenses', 'data':[m['expenses'] for m in monthly_summary], 'color':'red'},
                {'label':'Incomes', 'data':[m['incomes'] for m in monthly_summary], 'color':'green'}
            ]
        )

        yearly_chart = ChartGenerator('Yearly Income vs Expense', 'bar').plot(
            [y['period'] for y in yearly_summary],
            [
                {'label':'Expenses', 'data':[y['expenses'] for y in yearly_summary], 'color':'orange'},
                {'label':'Incomes', 'data':[y['incomes'] for y in yearly_summary], 'color':'blue'}
            ]
        )

        category_chart = ChartGenerator('Expenses by Category', 'pie').plot(
            [c['category__name'] for c in expense_category],
            [{'data':[c['total'] for c in expense_category],
              'colors':['#FF6384','#36A2EB','#FFCE56','#4BC0C0','#9966FF']}]
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
