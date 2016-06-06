# -*- coding: utf-8 -*-

""" Views for interacting with the PAYBOX payment processor. """

import json
import logging

import requests

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from oscar.apps.partner import strategy
from oscar.apps.payment.exceptions import PaymentError, UserCancelled, TransactionDeclined
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors.paybox_system import PayboxSystem

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')

Selector = get_class('partner.strategy', 'Selector')


class PayboxSystemNotifyView(EdxOrderPlacementMixin, View):
    """ Validates a response from Paybox and processes the associated basket/order appropriately. """
    payment_processor = PayboxSystem()

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(PayboxSystemNotifyView, self).dispatch(request, *args, **kwargs)

    def _get_basket(self, basket_id):
        try:
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = Selector().strategy(user=basket.owner)
        except Basket.DoesNotExist:
            basket = None
        return basket

    def post(self, request):
        """Process a Paybox merchant notification and place an order for paid products as appropriate."""

        # Note (CCB): Orders should not be created until the payment processor has validated the response's signature.
        # This validation is performed in the handle_payment method. After that method succeeds, the response can be
        # safely assumed to have originated from CyberSource.
        paybox_response = request.POST.dict()

        logger.info(paybox_response)

        basket = None
        transaction_id = None

        try:
            transaction_id = paybox_response.get('transaction-paybox')    # paybox transaction id
            order_number = paybox_response.get('reference-fun')     # edx/fun transaction (FUN-10XXX)
            basket_id = OrderNumberGenerator().basket_id(order_number)   # retrieve django ID of basket instance

            logger.info(
                'Received Paybox merchant notification for transaction [%s], associated with basket [%d].',
                transaction_id,
                basket_id
            )

            basket = self._get_basket(basket_id)
            if not basket:
                logger.error('Received payment for non-existent basket [%s].', basket_id)
                return HttpResponse(status=400)
        finally:
            # Store the response in the database regardless of its authenticity.
            ppr = self.payment_processor.record_processor_response(paybox_response, transaction_id=transaction_id,
                                                                   basket=basket)

        try:
            # Explicitly delimit operations which will be rolled back if an exception occurs.
            with transaction.atomic():
                try:
                    self.handle_payment(paybox_response, basket)
                except (UserCancelled, TransactionDeclined) as exception:
                    logger.info(
                        'Paybox payment did not complete for basket [%d] because [%s]. '
                        'The payment response was recorded in entry [%d].',
                        basket.id,
                        exception.__class__.__name__,
                        ppr.id
                    )
                    return HttpResponse()
        except:  # pylint: disable=bare-except
            logger.exception('Attempts to handle payment for basket [%d] failed.', basket.id)
            return HttpResponse(status=500)

        try:
            # no shipping fees
            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)

            # Note (CCB): This calculation assumes the payment processor has not sent a partial authorization,
            # thus we use the amounts stored in the database rather than those received from the payment processor.
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

            self.handle_order_placement(
                order_number=order_number,
                user=basket.owner,
                basket=basket,
                shipping_address=None,
                billing_address=None,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                order_total=order_total,
            )
        except:  # pylint: disable=bare-except
            logger.exception(self.order_placement_failure_msg, basket.id)
            return HttpResponse(status=500)

        # Notify fun-apps of transaction result
        url = settings.FUNAPPS_NOTIFY
        data = {
            'username': basket.owner.username,
            'email': basket.owner.email,
            'order_number': order_number
            }
        headers = {
            'Content-Type': 'application/json',
            'X-Edx-Api-Key': settings.EDX_API_KEY
            }

        response = requests.post(url, data=json.dumps(data), headers=headers, timeout=30)
        if response.status_code in (200, 201):
            logger.info(u'Notified fun-apps of %s order SUCCESS for user %s/%s.',
                    order_number, basket.owner.username, basket.owner.email)
        else:
            logger.info(u'Notified fun-apps of %s(%d) order FAIL for user %s/%s.',
                    order_number, response.status_code, basket.owner.username, basket.owner.email)

        return HttpResponse()
