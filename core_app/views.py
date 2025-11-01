from django.shortcuts import render, redirect
from .models import Expense
from .forms import ExpenseForm
from django.db.models import Sum
from datetime import date
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required

@login_required(login_url='/login/')  
def dashboard(request):
    expenses = Expense.objects.filter(user=request.user)

    total = expenses.aggregate(Sum('amount'))['amount__sum'] or 0


    today = date.today()
    current_month_expenses = expenses.filter(date__year=today.year, date__month=today.month)
    category_summary = current_month_expenses.values('category__name').annotate(total=Sum('amount'))


    monthly_summary = expenses.annotate(month=TruncMonth('date')) \
                              .values('month').annotate(total=Sum('amount'))

    context = {
        'expenses': expenses,
        'total': total,
        'category_summary': category_summary,
        'monthly_summary': monthly_summary
    }
    return render(request, 'dashboard.html', context)


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

def edit_expense(request, expense_id):
    expense = Expense.objects.get(id=expense_id)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = ExpenseForm(instance=expense)
    return render(request, 'edit_expense.html', {'form': form})

def delete_expense(request, expense_id):
    expense = Expense.objects.get(id=expense_id)
    expense.delete()
    return redirect('dashboard')
