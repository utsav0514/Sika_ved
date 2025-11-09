from django.db.models import Sum
from datetime import datetime
from collections import defaultdict
import calendar

class BudgetBalancer:
    """
    Enhanced algorithm for detailed budget analysis.
    """

    def __init__(self, incomes, expenses):
        """
        :param incomes: list or queryset of Income objects
        :param expenses: list or queryset of Expense objects
        """
        self.incomes = list(incomes)
        self.expenses = list(expenses)

    def analyze(self):
        """Return a detailed summary including totals, category distribution, and monthly trends"""
        # ---------------- TOTALS ----------------
        # FIX: sum by amount field instead of objects
        total_income = sum(inc.amount for inc in self.incomes)
        total_expense = sum(exp.amount for exp in self.expenses)
        balance = total_income - total_expense
        savings_ratio = round((balance / total_income) * 100, 2) if total_income else 0

        if balance > 0:
            status = f"🟢 Within budget — You are saving {savings_ratio}% of your income."
        elif balance == 0:
            status = "🟡 Breaking even — No savings this month."
        else:
            status = f"🔴 Overspent — You are over budget by ₹{abs(balance)}."

        # ---------------- EXPENSE DISTRIBUTION ----------------
        category_totals = defaultdict(float)
        for exp in self.expenses:
            cat_name = getattr(exp.category, 'name', 'Uncategorized')
            category_totals[cat_name] += exp.amount

        category_distribution = []
        for cat, amt in category_totals.items():
            perc = round((amt / total_expense) * 100, 2) if total_expense else 0
            category_distribution.append({
                'category': cat,
                'amount': amt,
                'percentage': perc
            })

        # Sort categories descending by amount
        category_distribution.sort(key=lambda x: x['amount'], reverse=True)

        # ---------------- MONTHLY TREND ----------------
        monthly_data = defaultdict(lambda: {'income': 0, 'expense': 0})
        for inc in self.incomes:
            month_key = inc.date.strftime('%b %Y')
            monthly_data[month_key]['income'] += inc.amount

        for exp in self.expenses:
            month_key = exp.date.strftime('%b %Y')
            monthly_data[month_key]['expense'] += exp.amount

        monthly_trend = []
        for month, data in sorted(monthly_data.items(), key=lambda x: datetime.strptime(x[0], '%b %Y')):
            month_income = data['income']
            month_expense = data['expense']
            month_balance = month_income - month_expense
            monthly_trend.append({
                'month': month,
                'income': month_income,
                'expense': month_expense,
                'balance': month_balance
            })

        # ---------------- INSIGHTS ----------------
        insights = []

        # Check if overspending occurred in any month
        for month_data in monthly_trend:
            if month_data['balance'] < 0:
                insights.append(
                    f"You overspent in {month_data['month']} by ₹{abs(month_data['balance'])} — check big expenses."
                )

        # Check top spending category
        if category_distribution:
            top_cat = category_distribution[0]
            if top_cat['percentage'] > 50:
                insights.append(
                    f"Most expenses are on {top_cat['category']} ({top_cat['percentage']}%) — consider reducing or spreading it."
                )

        if not insights:
            insights.append("Your spending is balanced. Keep up the good work!")

        # ---------------- FINAL OUTPUT ----------------
        return {
            'budget_status': {
                'total_income': total_income,
                'total_expense': total_expense,
                'balance': balance,
                'savings_ratio': savings_ratio,
                'status': status
            },
            'expense_distribution': category_distribution,
            'monthly_trend': monthly_trend,
            'insights': insights
        }

    def suggest_budget_plan(self):
        """Optional: provide a simple summary suggestion"""
        data = self.analyze()
        return data['budget_status']['status']
