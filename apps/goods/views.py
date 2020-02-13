# -*-coding:utf-8-*-
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View

from apps.goods.models import GoodsType, GoodsSKU, \
    IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from apps.order.models import OrderGoods

from django_redis import get_redis_connection
from django.core.paginator import Paginator
from django.core.cache import cache


# Create your views here.
from dailydemo2.settings import HAYSTACK_SEARCH_RESULTS_PER_PAGE


class IndexView(View):
    """首页"""

    def get(self, request):
        """显示首頁"""
        # 先判断缓存中是否有数据,没有数据不会报错返回None
        context = cache.get('index_page_data')

        if context is None:  # 代表缓存中没有数据
            # 获取商品的种类信息
            types = GoodsType.objects.all()
            # 获取首页轮播的商品的信息
            index_banner = IndexGoodsBanner.objects.all().order_by('index')  # 升序
            # 获取首页促销的活动信息
            promotion_banner = IndexPromotionBanner.objects.all().order_by('index')

            # 获取首页分类商品信息展示
            for type in types:  # GoodType
                # 获取type种类在首页分类商品的文字展示信息
                title_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
                # 获取type种类在首页分类商品的图片展示信息
                image_banner = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
                # 动态给type增加属性，分别保存首页商品的图片与文字的展示信息(这不会影响到db)
                type.title_banner = title_banner
                type.image_banner = image_banner
            # 组织上下文
            context = {
                'types': types,
                'index_banner': index_banner,
                'promotion_banner': promotion_banner,
            }
        # 设置缓存数据,缓存的名字，内容，过期的时间
        cache.set('index_page_data', context, 600)

        # 获取user
        user = request.user
        # 获取登录用户的额购物车中的商品的数量
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id
            cart_count = conn.hlen(cart_key)
            # cart_count = CartInfo.objects.filter(user_id=int(user.id)).count()

        # 获取用户购物车中的商品数目
        context.update(cart_count=cart_count)

        return render(request, 'df_goods/index.html', context)


# /goods/商品id
class DetailView(View):
    """详情页"""

    def get(self, request, goods_id):
        # 查询是否有该商品id
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()

        # 获取商品的评论信息(排除评论为空)
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')

        # 获取新品推荐信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:3]  # 降序排列

        # 获取同一个SPU的其他规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)  # 排除自己

        # 获取登录用户的额购物车中的商品的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            # 获取用户购物车中的商品条目数
            cart_count = conn.hlen(cart_key)  # hlen hash中的数目

            # 添加用户的历史记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id
            # 移除列表中的goods_id
            conn.lrem(history_key, 0, goods_id)
            # 把goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保存用户最新浏览的5条信息
            conn.ltrim(history_key, 0, 4)

        # 组织模版上下文
        context = {'sku': sku, 'types': types,
                   'sku_orders': sku_orders,
                   'new_skus': new_skus,
                   'same_spu_skus': same_spu_skus,
                   'cart_count': cart_count}

        return render(request, 'df_goods/detail.html', context)


# 种类id 页码 排序方式
# restful api -> 请求一种资源
# /list?type_id=种类id&page=页码&sort=排序方式
# /list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式 => 本网站使用方式
class ListView(View):
    """列表页"""

    def get(self, request, type_id, page):
        # 先获取种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 种类不存在
            return redirect(reverse('goods:index'))

        # 获取商品的分类信息
        types = GoodsType.objects.all()

        # 获取排序方式  获取分类商品的信息
        # sort=default,按默认id排序; sort=price,按价格; sort=hot,按销量;
        sort = request.GET.get('sort')

        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')  # 默认

        # 对数据进行分页
        paginator = Paginator(skus, HAYSTACK_SEARCH_RESULTS_PER_PAGE)
        try:
            page = int(page)
        except Exception as e:
            page = 1

        if page > paginator.num_pages or page <= 0:
            page = 1

        # 获取第page页的Page实例对象
        skus_page = paginator.page(page)

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

        # 获取新品推荐信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')

        # 获取登录用户的额购物车中的商品的数量
        user = request.user
        cart_count = 0
        if user.is_authenticated:
            # 用户已经登录
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            # 获取用户购物车中的商品条目数
            cart_count = conn.hlen(cart_key)  # hlen hash中的数目

        # 组织模版上下文
        context = {'type': type, 'types': types,
                   'sort': sort,
                   'skus_page': skus_page,
                   'new_skus': new_skus,
                   'pages': pages,
                   'cart_count': cart_count}

        return render(request, 'df_goods/list.html', context)
