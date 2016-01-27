from __future__ import unicode_literals

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest, HttpResponseServerError

from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import

from ecommerce.coupons.views import get_voucher
from ecommerce.extensions.api.data import get_lms_footer
from ecommerce.extensions.basket.utils import prepare_basket, get_product_from_sku
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.settings import get_lms_url

from edx_rest_api_client.client import EdxRestApiClient
from edx_rest_api_client.exceptions import SlumberHttpBaseException

Basket = get_model('basket', 'Basket')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')


class BasketSingleItemView(View):
    def get(self, request):
        partner = get_partner_for_site(request)
        if not partner:
            return HttpResponseServerError('No Partner is associated with this site.')

        sku = request.GET.get('sku', None)
        code = request.GET.get('code', None)

        if not sku:
            return HttpResponseBadRequest('No SKU provided.')

        if code:
            voucher, _ = get_voucher(code=code)
        else:
            voucher = None

        product, msg = get_product_from_sku(partner=partner, sku=sku)

        if product is None:
            return HttpResponseBadRequest(msg)

        purchase_info = request.strategy.fetch_for_product(product)
        if not purchase_info.availability.is_available_to_buy:
            return HttpResponseBadRequest('SKU [{}] does not exist.'.format(sku))

        prepare_basket(request, request.user, product, voucher)

        # Redirect to payment page
        return HttpResponseRedirect(reverse('basket:summary'), status=303)


class BasketSummaryView(BasketView):
    def get_context_data(self, **kwargs):
        context = super(BasketSummaryView, self).get_context_data(**kwargs)
        lines = context['line_list']
        courses = {}
        api = EdxRestApiClient(
            get_lms_url('api/courses/v1/'),
        )
        for line in lines:
            course_id = line.product.course_id
            try:
                course = api.courses(course_id).get()
                course['image_url'] = get_lms_url(course['media']['course_image']['uri'])
                line.course = course
            except SlumberHttpBaseException as e:
                logger.exception('Could not get course information. [%s]', e)

        context.update({
            'course': courses,
            'payment_processors': self.get_payment_processors(),
            'homepage_url': get_lms_url(''),
            'footer': get_lms_footer()
        })
        return context

    def get_payment_processors(self):
        """ Retrieve the list of active payment processors. """
        # TODO Retrieve this information from SiteConfiguration
        processors = (get_processor_class(path) for path in settings.PAYMENT_PROCESSORS)
        return [processor for processor in processors if processor.is_enabled()]
