from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.views.generic import View
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail
from django_redis import get_redis_connection

from apps.user.models import User, Address, GoodsBrowser
from apps.goods.models import GoodsSKU
from apps.order.models import OrderInfo, OrderGoods
from celery_tasks.tasks import send_register_active_email
from utils.mixin import LoginRequireMixin

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
import re


# /user/register
def register(request):
    """注册"""
    if request.method == 'GET':
        return render(request, 'df_user/register.html')  # 显示注册页面
    else:
        # 进行注册处理
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'df_user/register.html', {'errmsg': '数据不完整'})

        # 检验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'df_user/register.html', {'errmsg': '邮箱格式不正确'})

        # 检验密码是否一致
        if password != cpassword:
            return render(request, 'df_user/register.html', {'errmsg': '两次输入的密码不一致'})

        # 检验是否同意协议
        if allow != 'on':
            return render(request, 'df_user/register.html', {'errmsg': '请同意协议'})

        # 校验用户是否重复
        try:
            existUser = User.objects.get(username=username)
        except existUser.DoesNotExist:
            # 用户名不存在
            existUser = None

        if existUser:
            return render(request, 'df_user/register.html', {'errmsg': '用户已存在'})

        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 返回应答,跳转首页
        return redirect(reverse('goods:index'))


class RegisterView(View):
    """注册"""

    def get(self, request):
        # 显示注册页面
        return render(request, 'df_user/register.html')

    def post(self, request):
        # 进行注册处理
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')

        # 进行 数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'df_user/register.html', {'errmsg': '数据不完整'})

        # 检验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'df_user/register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'df_user/register.html', {'errmsg': '请同意协议'})

        # 校验用户是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        if user:
            return render(request, 'df_user/register.html', {'errmsg': '用户已存在'})

        # 进行业务处理：进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活链接，包含激活链接：http://127.0.0.1:8000/user/active/5
        # 激活链接中需要包含用户的身份信息，并要把身份信息进行加密
        # 激活链接格式: /user/active/用户身份加密后的信息 /user/active/token

        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)  # bytes
        token = token.decode('utf8')  # 解码, str

        # 找其他人帮助我们发送邮件 celery:异步执行任务
        send_register_active_email.delay(email, username, token)

        # 返回应答,跳转首页
        return redirect(reverse('goods:index'))


# /user/active/加密信息token
class ActiveView(View):
    """用户激活"""

    def get(self, request, token):
        # 进行用户激活
        # 进行解密，获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']

            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse('激活链接已失效')


# /user/login
class LoginView(View):
    """登录"""

    def get(self, request):
        # 显示登录页面
        # 判断是否记住密码
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')  # request.COOKIES['username']
            checked = 'checked'
        else:
            username = ''
            checked = ''

        return render(request, 'df_user/login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """登录校验"""
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # remember = request.POST.get('remember')  # on

        # 校验数据
        if not all([username, password]):
            return render(request, 'df_user/login.html', {'errmsg': '数据不完整'})

        # 业务处理: 登陆校验
        user = authenticate(username=username, password=password)  # 这边就会帮忙加密了，不用再加密验证
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 登录并记录用户的登录状态
                login(request, user)

                # 获取登录后所要跳转到的地址
                # 默认跳转首页
                next_url = request.GET.get('next', reverse('goods:index'))

                #  跳转到next_url
                response = redirect(next_url)  # HttpResponseRedirect

                # 设置cookie, 需要通过HttpReponse类的实例对象, set_cookie
                # HttpResponseRedirect JsonResponse

                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                else:
                    response.delete_cookie('username')

                # 回应 response
                return response

            else:
                # 用户未激活
                # print("The passwoed is valid, but the account has been disabled!")
                return render(request, 'df_user/login.html', {'errmsg': '账户未激活'})
        else:
            return render(request, 'df_user/login.html', {'errmsg': '用户名或密码错误'})


# /user/logout
class LogoutView(View):
    """退出登录"""

    def get(self, request):
        """退出"""
        # 清除用户的session信息
        logout(request)
        # 跳转到首页
        return redirect(reverse('goods:index'))


# /user
# LoginRequireMixin => 先调用LoginRequireMixin的as_view，之后再调用View里面的as_view，最后反馈时包装login_required
class UserInfoView(LoginRequireMixin, View):
    """用户中心-信息页"""

    def get(self, request):
        """显示"""
        # request.user.is_authenticated()
        # 如果用户未登入→AnonymousUser类的一个实例
        # 如果用户登入→User类的一个实例
        # 除了你给模板文件传递的模板变量之外，django框架会把request.user也传给模板文件(直接在模板内使用request.user.is_authenticated

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        con = get_redis_connection('default')

        history_key = 'history_%d' % user.id

        # 获取用户最新历史浏览记录的5个商品id
        sku_ids = con.lrange(history_key, 0, 4)

        # 遍历获取用户浏览的历史商品信息
        goods_list = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_list.append(goods)

        # 组织上下文
        context = {'page': 'user',
                   'address': address,
                   'goods_list': goods_list}
        return render(request, 'df_user/user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequireMixin, View):
    """用户中心-订单页"""

    def get(self, request, page):
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user)

        # 遍历获取订单商品的信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                # 计算小计
                amount = order_sku.count * order_sku.price
                # 动态给order_sku增加属性amount，保存订单商品的小计
                order_sku.amount = amount

            # 动态给order增加属性，保存订单状态的标题
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 2)
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages or page <= 0:
            page = 1

        # 获取第page页的Page实例对象
        order_page = paginator.page(page)

        # todo: 进行页码的控制，页面上最多显示5个页码
        # 1. 总数不足5页，显示全部
        # 2. 如当前页是前3页，显示1-5页
        # 3. 如当前页是后3页，显示后5页
        # 4. 其他情况，显示当前页的前2页，当前页，当前页的后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'
                   }

        return render(request, 'df_user/user_center_order.html', context)


# /user/address
class AddressView(LoginRequireMixin, View):
    """用户中心-地址页"""

    def get(self, request):
        # 获取用户的默认收货地址
        user = request.user

        address = Address.objects.get_default_address(user)

        try:
            otherAddress = Address.objects.get(user=user, is_default=False)
        except Address.DoesNotExist:
            # 不存在默认收货地址
            otherAddress = None

        # 使用模板
        return render(request, 'df_user/user_center_site.html',
                      {'page': 'address', 'address': address, 'otherAddress': otherAddress})

    def post(self, request):
        """地址的添加"""
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'df_user/user_center_site.html', {'errmsg': '数据不完整'})

        # 校验手机号
        if not re.match(r'^[1][3,4,5,7,8][0-9]{9}$', phone):
            return render(request, 'df_user/user_center_site.html', {'errmsg': '手机号格式不正确'})

        # 业务处理：地址添加
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        # 获取登入用户对应的User对象
        user = request.user
        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone, is_default=is_default)

        # 返回应答，刷新地址页面
        return redirect(reverse('user:address'))
