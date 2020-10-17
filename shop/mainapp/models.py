from PIL import Image
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


def get_models_get_count(*model_names):
    return [models.Count(model_name) for model_name in model_names]


def get_product_url(obj, viewname):
    ct_model = obj.__class__._meta.model_name
    return reverse(viewname, kwargs={'ct_model': ct_model, 'slug': obj.slug})


class MinResolutionErrorException(Exception):
    pass


class MaxResolutionErrorException(Exception):
    pass


class LatestProductsManager:
    @staticmethod
    def get_products_for_main_page(*args, **kwargs):
        with_respect_to = kwargs.get('with_respect_to')
        products = []
        ct_models = ContentType.objects.filter(model__in=args)
        for ct_model in ct_models:
            model_products = ct_model.model_class()._base_manager.all().order_by('-id')[:5]
            products.extend(model_products)
        if with_respect_to:
            ct_model = ContentType.objects.filter(model=with_respect_to)
            if ct_model.exists():
                if with_respect_to in args:
                    return sorted(
                        products, key=lambda x: x.__class__._meta.model_name.startswith(with_respect_to), reverse=True
                    )
        return products


class LatestProducts:
    objects = LatestProductsManager


class CategoryManager(models.Manager):

    CATEGORY_NAME_COUNT_NAME = {
        'Ноутбуки': 'notebook__count',
        'Смартфоны': 'smartphone__count'
    }

    def get_queryset(self):
        return super().get_queryset()

    def get_categories_for_left_sidebar(self):
        models = get_models_get_count('notebook', 'smartphone')
        qs = list(self.get_queryset().annotate(*models))
        data = [
            dict(name=c.name, url=c.get_absolute_url(), count=getattr(c, self.CATEGORY_NAME_COUNT_NAME[c.name]))
            for c in qs
        ]
        return data


class Category(models.Model):
    name = models.CharField(max_length=255, verbose_name="Имя категории")
    slug = models.SlugField(unique=True, verbose_name="URL")
    objects = CategoryManager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category_detail', kwargs={'slug': self.slug})

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"


class Product(models.Model):

    MIN_RESOLUTION = (300, 300)
    MAX_RESOLUTION = (2500, 2500)
    MAX_IMAGE_SIZE = 3145728

    class Meta:
        abstract = True
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"

    category = models.ForeignKey(Category, verbose_name="Категория", on_delete=models.CASCADE)
    title = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(unique=True, verbose_name="URL")
    image = models.ImageField(verbose_name="Фото", blank=True)
    description = models.TextField(verbose_name="Описание", null=True)
    price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name="Цена", blank=True)

    def __str__(self):
        return self.title

    def get_model_name(self):
        return self.__class__.__name__.lower()

    def save(self, *args, **kwargs):
        image = self.image
        img = Image.open(image)
        min_height, min_width = self.MIN_RESOLUTION
        max_height, max_width = self.MAX_RESOLUTION
        if img.height < min_height or img.width < min_width:
            raise MinResolutionErrorException('Разрешение фото меньше минимального')
        if img.height > max_height or img.width > max_width:
            raise MaxResolutionErrorException('Разрешение фото больше максимального')
        super().save(*args, **kwargs)


class CartProduct(models.Model):
    user = models.ForeignKey('Customer', verbose_name="Покупатель", on_delete=models.CASCADE, related_name="related_users")
    cart = models.ForeignKey('Cart', verbose_name="Корзина", on_delete=models.CASCADE, related_name="related_products")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    qty = models.PositiveIntegerField(default=1)
    final_price = models.DecimalField(max_digits=9, decimal_places=2, verbose_name="Общая цена")

    def __str__(self):
        return "Продукт: {} (для корзины)".format(self.content_object.title)

    def save(self, *args, **kwargs):
        self.final_price = self.qty * self.content_object.price
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Корзина товара"
        verbose_name_plural = "Корзина товара"


class Cart(models.Model):
    owner = models.ForeignKey('Customer', null=True, verbose_name="Владелец", on_delete=models.CASCADE)
    products = models.ManyToManyField(CartProduct, blank=True, related_name="related_cart")
    total_products = models.PositiveIntegerField(default=0)
    final_price = models.DecimalField(max_digits=9, default=0, decimal_places=2, verbose_name="Общая цена")
    in_order = models.BooleanField(default=False)
    for_anonymous_user = models.BooleanField(default=False)

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзина"


class Customer(models.Model):
    user = models.ForeignKey(User, verbose_name="Пользователь", on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, verbose_name="Номер телефона", null=True, blank=True)
    address = models.CharField(max_length=255, verbose_name="Адрес", null=True, blank=True)
    orders = models.ManyToManyField('Order', verbose_name="Заказы покупателя", related_name="related_customer")

    def __str__(self):
        return "Покупатель: {} {}".format(self.user.first_name, self.user.last_name)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class Order(models.Model):

    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_READY = 'is_ready'
    STATUS_COMPLETED = 'completed'

    BUYING_TYPE_SELF = 'self'
    BUYING_TYPE_DELIVERY = 'delivery'

    STATUS_CHOICES = (
        (STATUS_NEW, 'Новый заказ'),
        (STATUS_IN_PROGRESS, 'Заказ в обработке'),
        (STATUS_READY, 'Заказ готов'),
        (STATUS_COMPLETED, 'Заказ выполнен')
    )

    BUYING_TYPE_CHOICES = (
        (BUYING_TYPE_SELF, 'Самовывоз'),
        (BUYING_TYPE_DELIVERY, 'Доставка')
    )

    customer = models.ForeignKey(Customer, verbose_name="Покупатель", related_name='related_orders', on_delete=models.CASCADE)
    first_name = models.CharField(max_length=255, verbose_name="Имя")
    last_name = models.CharField(max_length=255, verbose_name="Фамилие")
    phone = models.CharField(max_length=20, verbose_name="Номер телефона")
    cart = models.ForeignKey(Cart, verbose_name="Корзина", on_delete=models.CASCADE, null=True, blank=True)
    address = models.CharField(max_length=1024, verbose_name="Адрес", null=True, blank=True)
    status = models.CharField(
        max_length=100, verbose_name="Статус заказа", choices=STATUS_CHOICES, default=STATUS_NEW
    )
    buying_type = models.CharField(
        max_length=100, verbose_name="Тип заказа", choices=BUYING_TYPE_CHOICES, default=BUYING_TYPE_SELF
    )
    comment = models.TextField(verbose_name="Комментарии к заказу", null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True, verbose_name="Дата создания заказа")
    order_date = models.DateField(verbose_name="Дата получения заказа", default=timezone.now)

    def __str__(self):
        return str(self.id)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"


class Notebook(Product):
    diagonal = models.CharField(max_length=255, verbose_name="Диагональ", blank=True)
    display_type = models.CharField(max_length=255, verbose_name="Тип дисплея", blank=True)
    processor_freq = models.CharField(max_length=255, verbose_name="Частота процессора", blank=True)
    ram = models.CharField(max_length=255, verbose_name="Оперативная память", blank=True)
    video = models.CharField(max_length=255, verbose_name="Видеокарта", blank=True)
    time_without_charge = models.CharField(max_length=255, verbose_name="Время работы аккумулятора", blank=True)

    def __str__(self):
        return "{} : {}".format(self.category.name, self.title)

    def get_absolute_url(self):
        return get_product_url(self, 'product_detail')

    class Meta:
        verbose_name = "Ноутбук"
        verbose_name_plural = "Ноутбуки"


class Smartphone(Product):
    diagonal = models.CharField(max_length=255, verbose_name="Диагональ", blank=True)
    display_type = models.CharField(max_length=255, verbose_name="Тип дисплея", blank=True)
    resolution = models.CharField(max_length=255, verbose_name="Разрешение экрана", blank=True)
    accum_volume = models.CharField(max_length=255, verbose_name="Объем батареи", blank=True)
    ram = models.CharField(max_length=255, verbose_name="Оперативная память", blank=True)
    sd = models.BooleanField(default=True, verbose_name="Наличие SD карта")
    sd_volume = models.CharField(
        max_length=255, null=True, verbose_name="Макс. объём встраиваемой памяти", blank=True
    )
    main_cam = models.CharField(max_length=255, verbose_name="Передняя камера", blank=True)
    front_cam = models.CharField(max_length=255, verbose_name="Фронтальная камера", blank=True)

    def __str__(self):
        return "{} : {}".format(self.category.name, self.title)

    def get_absolute_url(self):
        return get_product_url(self, 'product_detail')

    class Meta:
        verbose_name = "Смартфон"
        verbose_name_plural = "Смартфоны"




