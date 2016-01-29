import datetime
from decimal import Decimal
import json

import httpretty
from django.core.urlresolvers import reverse
import factory
from oscar.core.loading import get_class, get_model
from oscar.test import newfactories as factories
import pytz

from ecommerce.settings import get_lms_url
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Selector = get_class('partner.strategy', 'Selector')
SiteConfiguration = get_model('core', 'SiteConfiguration')


# TODO Create our own factories to support multi-tenancy
class PartnerFactory(factory.DjangoModelFactory):
    name = factory.Sequence(lambda n: 'Partner %d' % n)
    short_code = factory.Sequence(lambda n: 'P_%d' % n)

    class Meta:
        model = get_model('partner', 'Partner')

    @factory.post_generation
    def users(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for user in extracted:
                self.users.add(user)


class StockRecordFactory(factory.DjangoModelFactory):
    partner = factory.SubFactory(PartnerFactory)
    partner_sku = factory.Sequence(lambda n: 'unit%d' % n)
    price_currency = "GBP"
    price_excl_tax = Decimal('9.99')
    num_in_stock = 100

    class Meta:
        model = get_model('partner', 'StockRecord')


class BasketSingleItemViewTests(TestCase):
    path = reverse('basket:single-item')

    def setUp(self):
        super(BasketSingleItemViewTests, self).setUp()
        password = 'password'
        self.user = factories.UserFactory(password=password)
        self.client.login(username=self.user.username, password=password)

        product = factories.ProductFactory()
        self.stock_record = StockRecordFactory(product=product, partner=self.partner)

    def test_login_required(self):
        """ The view should require the user to be logged in. """
        self.client.logout()
        response = self.client.get(self.path)
        testserver_url = self.get_full_url(reverse('login'))
        expected_url = '{path}?next={basket_path}'.format(path=testserver_url, basket_path=self.path)
        self.assertRedirects(response, expected_url, target_status_code=302)

    # # TODO Add the partner to the request using middleware
    # def test_missing_partner(self):
    #     """ The view should return HTTP 500 if the site has no associated Partner. """
    #     site_configuration = SiteConfigurationFactory()
    #     site = site_configuration.site
    #     # site.siteconfiguration = site_configuration
    #     request = RequestFactory()
    #     request.site = site

    #     response = BasketSingleItemView().get(request)
    #     self.assertEqual(response.status_code, 400)
    #     # self.assertEqual(response.content, 1)

    def test_missing_sku(self):
        """ The view should return HTTP 400 if no SKU is provided. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)

    def test_unavailable_product(self):
        """ The view should return HTTP 400 if the product is not available for purchase. """
        product = self.stock_record.product
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()
        self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)

        url = '{path}?sku={sku}'.format(path=self.path, sku=self.stock_record.partner_sku)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    @httpretty.activate
    def assert_view_redirects_to_checkout_payment(self):
        """ Verify the view redirects to the checkout payment page. """
        url = '{path}?sku={sku}'.format(path=self.path, sku=self.stock_record.partner_sku)
        course_info = {
            "media": {
                "course_image": {
                    "uri": "/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg"
                }
            },
        }
        course_info_json = json.dumps(course_info)
        course_url = get_lms_url('api/courses/v1/courses/')
        httpretty.register_uri(httpretty.GET, course_url, body=course_info_json, content_type='application/json')
        response = self.client.get(url)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url, status_code=303)

    def test_redirect(self):
        """ The view should redirect the user to the payment page. """
        self.assert_view_redirects_to_checkout_payment()

    def test_basket(self):
        """ The user's latest Basket should contain one instance of the specified product and be frozen. """
        self.assert_view_redirects_to_checkout_payment()

        basket = Basket.get_basket(self.user, self.site)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, self.stock_record.product)
