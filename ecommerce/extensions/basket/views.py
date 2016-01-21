from __future__ import unicode_literals

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest, HttpResponseServerError

from oscar.apps.basket.views import *  # pylint: disable=wildcard-import, unused-wildcard-import

from ecommerce.coupons.views import get_voucher
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.payment.helpers import get_processor_class
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.settings import get_lms_url

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

        # Make sure the SKU exists
        try:
            stock_record = StockRecord.objects.get(partner=partner, partner_sku=sku)
        except StockRecord.DoesNotExist:
            msg = 'SKU [{sku}] does not exist for partner [{name}].'.format(sku=sku, name=partner.name)
            return HttpResponseBadRequest(msg)

        # Make sure the product can be purchased
        product = stock_record.product
        purchase_info = request.strategy.fetch_for_product(product)
        if not purchase_info.availability.is_available_to_buy:
            return HttpResponseBadRequest('SKU [{}] does not exist.'.format(sku))

        prepare_basket(request, request.user, product, voucher)

        # Redirect to payment page
        url = reverse('basket:summary')
        return HttpResponseRedirect(url, status=303)


class BasketSummaryView(BasketView):
    def get_context_data(self, **kwargs):
        context = super(BasketSummaryView, self).get_context_data(**kwargs)

        context.update({
            'payment_processors': self.get_payment_processors(),
            'homepage_url': get_lms_url('')
        })
        return context

    def get_payment_processors(self):
        """ Retrieve the list of active payment processors. """
        # TODO Retrieve this information from SiteConfiguration
        processors = (get_processor_class(path) for path in settings.PAYMENT_PROCESSORS)
        return [processor for processor in processors if processor.is_enabled()]
