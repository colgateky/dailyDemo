from django.contrib import admin
from django.urls import path, include
from django.conf.urls import url
from django.views.static import serve  # 上传文件处理函数
from .settings import MEDIA_ROOT

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tinymce/', include('tinymce.urls')),  # 富文本编辑器
    path('user/', include('apps.user.urls', namespace='user')),  # 用户模块
    path('search/', include('haystack.urls')),  # 全文检索框架
    path('cart/', include('apps.cart.urls', namespace='cart')),  # 购物车模块
    path('order/', include('apps.order.urls', namespace='order')),  # 订单模块
    path('', include('apps.goods.urls', namespace='goods')),  # 商品模块
    url(r'^media/(?P<path>.*)$', serve, {"document_root": MEDIA_ROOT})

]
