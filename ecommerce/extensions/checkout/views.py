from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
# noinspection PyUnresolvedReferences
from oscar.apps.checkout.views import *  # pylint: disable=wildcard-import, unused-wildcard-import

from ecommerce.extensions.payment.helpers import get_processor_class


class PaymentView(TemplateView):
    """
    Checkout payment view.

    This view merges the existing payment details, preview, and confirmation views into one. The user will see the
    contents of the basket along with the payment UI needed to place the order.
    """
    template_name = 'checkout/payment.html'

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, *args, **kwargs):
        return super(PaymentView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PaymentView, self).get_context_data(**kwargs)
        basket = Basket.get_basket(self.request.user, self.request.site)

        context.update({
            'basket': basket,
            'payment_processors': self.get_payment_processors()
        })
        return context

    def get_payment_processors(self):
        """ Retrieve the list of active payment processors. """
        # TODO Retrieve this information from SiteConfiguration
        return [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]
