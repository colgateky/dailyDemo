# -*-coding:utf-8-*-
from django.conf.urls import url
# from apps.user import views

from apps.user.views import RegisterView, ActiveView, \
    LoginView, UserInfoView, UserOrderView, AddressView, LogoutView

app_name = 'apps.user'
urlpatterns = [
    url(r'^register/$', RegisterView.as_view(), name='register'),  # 注册页面
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),  # 用户激活

    url(r'^login/$', LoginView.as_view(), name='login'),  # 登录
    url(r'^logout/$', LogoutView.as_view(), name='logout'),  # 退出登录

    # 在url配置的时候，调用login_required装饰器，相当于配置的函数是login_required的返回值
    # url(r'^$',  (UserInfoView.as_view()), name='user'),  # 用户中心-信息页
    # url(r'^order/$', login_required(UserOrderView.as_view()), name='order'),  # 用户中心-订单页
    # url(r'^address/$', login_required(AddressView.as_view()), name='address'),  # 用户中心-地址页

    # 下面是将login_required拉出写在utils内部调用，功能跟上面的是一致的
    url(r'^$', UserInfoView.as_view(), name='user'),  # 用户中心-信息页
    url(r'^order/(?P<page>\d+)$', UserOrderView.as_view(), name='order'),  # 用户中心-订单页
    url(r'^address$', AddressView.as_view(), name='address'),  # 用户中心-地址页

]