from django.contrib import admin
from .models import Category, Expense, Income

# ========== Expense Category ==========
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


# ========== Expense ==========
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'amount', 'date', 'description')
    list_filter = ('category', 'date')
    search_fields = ('user__username', 'description')
    ordering = ('-date',)


# ========== Income ==========
@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'description', 'date')  # ✅ Added description
    list_filter = ('date',)
    search_fields = ('user__username', 'description')
    ordering = ('-date',)
