import datetime
import json

import httpretty
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import override_settings
from oscar.core.loading import get_class, get_model
from oscar.test import newfactories as factories
import pytz
from testfixtures import LogCapture
from waffle.models import Switch

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.settings import get_lms_url
from ecommerce.tests.factories import StockRecordFactory
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Selector = get_class('partner.strategy', 'Selector')

LOGGER_NAME = 'ecommerce.extensions.basket.views'


class BasketSingleItemViewTests(TestCase):
    """ BasketSingleItemView view tests. """
    path = reverse('basket:single-item')

    def setUp(self):
        super(BasketSingleItemViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        product = factories.ProductFactory()
        self.stock_record = StockRecordFactory(product=product, partner=self.partner)

    def test_login_required(self):
        """ The view should require the user to be logged in. """
        self.client.logout()
        response = self.client.get(self.path)
        testserver_url = self.get_full_url(reverse('login'))
        expected_url = '{path}?next={basket_path}'.format(path=testserver_url, basket_path=self.path)
        self.assertRedirects(response, expected_url, target_status_code=302)

    def test_missing_sku(self):
        """ The view should return HTTP 400 if no SKU is provided. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)

    def test_missing_product(self):
        """ The view should return HTTP 400 if SKU with no product is provided. """
        url = '{path}?sku={sku}'.format(path=self.path, sku='NONEXISTING')
        response = self.client.get(url)
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
            }
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


class BasketSummaryViewTests(TestCase):
    """ BasketSummaryView basket view tests. """
    path = reverse('basket:summary')

    def setUp(self):
        super(BasketSummaryViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory()

    def prepare_basket(self, product):
        """ Helper function for creating and adding a product to a basket. """
        basket = factories.BasketFactory(owner=self.user)
        basket.add_product(product, 1)
        self.assertEqual(basket.lines.count(), 1)
        return basket

    def prepare_course_api_response(self):
        """ Helper function to register an API endpoint for the course information. """
        course_info = {
            "media": {
                "course_image": {
                    "uri": "/asset-v1:edX+DemoX+Demo_Course+type@asset+block@images_course_image.jpg"
                }
            }
        }
        course_info_json = json.dumps(course_info)
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(self.course.id))
        httpretty.register_uri(httpretty.GET, course_url, body=course_info_json, content_type='application/json')

    def prepare_footer_api_response(self):
        """ Helper function to register an API endpoint for the footer information. """
        footer_url = get_lms_url('api/branding/v1/footer')
        footer_content = {
            'footer': 'edX Footer'
        }
        content_json = json.dumps(footer_content)
        httpretty.register_uri(httpretty.GET, footer_url, body=content_json, content_type='application/json')

    @httpretty.activate
    def test_connection_to_course_error(self):
        """ Verify a connection error is logged when a connection error happens. """
        self.prepare_footer_api_response()
        seat = self.course.create_or_update_seat('verified', True, 50, self.partner)
        self.prepare_basket(seat)
        course_url = get_lms_url('api/courses/v1/courses/')
        with LogCapture(LOGGER_NAME) as l:
            self.client.get(self.path)
            l.check(
                (
                    LOGGER_NAME, 'ERROR',
                    u'Could not get course information. [Client Error 404: {course_url}{course_id}/]'.format(
                        course_url=course_url, course_id=self.course.id
                    )
                )
            )

    @httpretty.activate
    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def test_response_success(self):
        """ Verify a successful response is returned. """
        seat = self.course.create_or_update_seat('verified', True, 50, self.partner)
        self.prepare_basket(seat)
        self.prepare_course_api_response()
        self.prepare_footer_api_response()

        switch, __ = Switch.objects.get_or_create(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME)
        switch.active = True
        switch.save()

        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['benefit'], '')
        self.assertEqual(response.context['payment_processors'][0].NAME, DummyProcessor.NAME)
        self.assertDictEqual(json.loads(response.context['footer']), {'footer': 'edX Footer'})
