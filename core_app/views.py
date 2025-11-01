from django.shortcuts import render, redirect, get_object_or_404
from .models import Expense
from .forms import ExpenseForm
from django.db.models import Sum
from datetime import date, timedelta
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required

@login_required(login_url='/login/')
def dashboard(request):
    expenses = Expense.objects.filter(user=request.user).order_by('-date')
    
    # Use latest expense date as "today" for dummy data
    if expenses.exists():
        today = expenses.order_by('-date').first().date
    else:
        today = date.today()

    # Today's expenses
    today_expenses = expenses.filter(date=today)
    today_total = today_expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    # Current week (last 7 days including latest expense date)
    start_of_this_week = today - timedelta(days=6)
    end_of_this_week = today
    this_week_expenses = expenses.filter(date__range=[start_of_this_week, end_of_this_week])
    this_week_total = this_week_expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    # Previous week (7 days before current week)
    start_of_last_week = start_of_this_week - timedelta(days=7)
    end_of_last_week = start_of_this_week - timedelta(days=1)
    last_week_expenses = expenses.filter(date__range=[start_of_last_week, end_of_last_week])
    last_week_total = last_week_expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    # Weekly difference
    weekly_difference = this_week_total - last_week_total
    weekly_difference_abs = abs(weekly_difference)

    # Current month
    start_of_this_month = today.replace(day=1)
    this_month_expenses = expenses.filter(date__gte=start_of_this_month)
    this_month_total = this_month_expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    # Previous month
    if start_of_this_month.month == 1:
        start_of_last_month = start_of_this_month.replace(year=start_of_this_month.year-1, month=12)
    else:
        start_of_last_month = start_of_this_month.replace(month=start_of_this_month.month-1)
    end_of_last_month = start_of_this_month - timedelta(days=1)
    last_month_expenses = expenses.filter(date__range=[start_of_last_month, end_of_last_month])
    last_month_total = last_month_expenses.aggregate(Sum('amount'))['amount__sum'] or 0

    # Category and monthly summary
    category_summary = expenses.values('category__name').annotate(total=Sum('amount'))
    monthly_summary = expenses.annotate(month=TruncMonth('date')) \
                              .values('month').annotate(total=Sum('amount')).order_by('month')

    context = {
        'expenses': expenses,
        'today_total': today_total,
        'this_week_total': this_week_total,
        'last_week_total': last_week_total,
        'weekly_difference': weekly_difference,
        'weekly_difference_abs': weekly_difference_abs,
        'this_month_total': this_month_total,
        'last_month_total': last_month_total,
        'category_summary': category_summary,
        'monthly_summary': monthly_summary,
    }
    return render(request, 'dashboard.html', context)

@login_required(login_url='/login/')
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.user = request.user
            expense.save()
            return redirect('dashboard')
    else:
        form = ExpenseForm()
    return render(request, 'add_expense.html', {'form': form})


@login_required(login_url='/login/')
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ExpenseForm(instance=expense)
    return render(request, 'edit_expense.html', {'form': form})


@login_required(login_url='/login/')
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
    expense.delete()
    return redirect('dashboard')


@login_required(login_url='/login/')
def reports(request):
    expenses = Expense.objects.filter(user=request.user)

    monthly_summary = expenses.annotate(month=TruncMonth('date')) \
                              .values('month') \
                              .annotate(total=Sum('amount')) \
                              .order_by('month')

    category_summary = expenses.values('category__name') \
                               .annotate(total=Sum('amount')) \
                               .order_by('-total')

    context = {
        'monthly_summary': monthly_summary,
        'category_summary': category_summary
    }
    return render(request, 'reports.html', context)


def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html  = template.render(context_dict)
    response = HttpResponse(content_type='application/pdf')
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


@login_required(login_url='/login/')
def reports_pdf(request):
    expenses = Expense.objects.filter(user=request.user)
    monthly_summary = expenses.annotate(month=TruncMonth('date')) \
                              .values('month').annotate(total=Sum('amount')).order_by('month')
    category_summary = expenses.values('category__name') \
                               .annotate(total=Sum('amount')).order_by('-total')
    
    context = {
        'monthly_summary': monthly_summary,
        'category_summary': category_summary
    }
    return render_to_pdf('reports_pdf.html', context)
