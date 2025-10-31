from django.contrib import admin
from .models import Category, Expense

# Category admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')         
    search_fields = ('name',)             


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'category', 'amount', 'date', 'description')  
    list_filter = ('category', 'date')    
    search_fields = ('user__username', 'description')  
    ordering = ('-date',)                  
