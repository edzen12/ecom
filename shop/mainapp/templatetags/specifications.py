from django import template
from django.utils.safestring import mark_safe

# from mainapp.models import Smartphone
from ..models import Smartphone


register = template.Library()


TABLE_HEAD = """
                <table class="table">
                    <tbody>
             """

TABLE_TAIL = """
                    </tbody>
                </table>   
             """

TABLE_CONTENT = """
                    <tr>
                        <td>{name}</td>
                        <td>{value}</td>
                    </tr>
                """

PRODUCT_SPEC = {
    'notebook': {
        'Диагональ': 'diagonal',
        'Тип дисплея': 'display_type',
        'Частота процессора': 'processor_freq',
        'Оперативная память': 'ram',
        'Видеокарта': 'video',
        'Время работы аккумулятора': 'time_without_charge',
    },
    'smartphone': {
        'Диагональ': 'diagonal',
        'Тип дисплея': 'display_type',
        'Разрешение экрана': 'resolution',
        'Объем батареи': 'accum_volume',
        'Оперативная память': 'ram',
        'SD карта': 'sd',
        'Макс. объём встраиваемой памяти': 'sd_volume',
        'Камера (МП)': 'main_cam',
        'Фронтальная камера (МП)': 'front_cam',
    }
}


def get_product_spec(product, model_name):
    table_content = ''
    for name, value in PRODUCT_SPEC[model_name].items():
        table_content += TABLE_CONTENT.format(name=name, value=getattr(product, value))
    return table_content


@register.filter
def product_spec(product):
    model_name = product.__class__._meta.model_name
    if isinstance(product, Smartphone):
        if not product.sd:
            PRODUCT_SPEC['smartphone'].pop('Максимальный объем SD карты', None)
        else:
            PRODUCT_SPEC['smartphone']['Макс. объём встраиваемой памяти'] = 'sd_volume'
    return mark_safe(TABLE_HEAD + get_product_spec(product, model_name) + TABLE_TAIL)

