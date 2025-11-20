from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from django.shortcuts import render

from core.utils import get_user_company
from p_v_App.models import Category, Products, Sales


@login_required
def home(request):
    user_company = get_user_company(request)
    today = timezone.localdate()

    if user_company:
        categories = Category.objects.filter(company=user_company).count()
        products = Products.objects.filter(company=user_company).count()
        today_sales = Sales.objects.filter(date_added__date=today, company=user_company)
    else:
        categories = 0
        products = 0
        today_sales = Sales.objects.none()

    context = {
        "page_title": "Início",
        "categories": categories,
        "products": products,
        "transaction": today_sales.count(),
        "total_sales": today_sales.aggregate(total=Sum("grand_total"))["total"] or 0,
    }
    return render(request, "core/home.html", context)


@login_required
def about(request):
    return render(request, "core/about.html", {"page_title": "Sobre"})
