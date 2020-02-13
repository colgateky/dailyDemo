# -*-coding:utf-8-*-
from django.contrib import admin
from apps.user.models import User, Address, GoodsBrowser

# Register your models here.

admin.site.register(User)
admin.site.register(Address)
admin.site.register(GoodsBrowser)