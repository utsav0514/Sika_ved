from django.db import models
from django.contrib.auth.models import User

# Expense category
class Category(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


# Income category
class IncomeCategory(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


# Expense model
class Expense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    amount = models.FloatField()
    description = models.TextField(blank=True, null=True)
    date = models.DateField()

    def __str__(self):
        return f"{self.user.username} - {self.category.name if self.category else 'No Category'} - {self.amount}"


# Income model
class Income(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.FloatField()
    date = models.DateField()

    def __str__(self):
        return f"{self.user.username} - {self.amount}"