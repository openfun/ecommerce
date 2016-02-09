# coding=utf-8
from __future__ import unicode_literals
import datetime
from decimal import Decimal
import json
import logging
from urlparse import urljoin, urlparse

from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
import httpretty
import mock
from oscar.core.loading import get_model
import pytz
from testfixtures import LogCapture

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.catalogue.management.commands.migrate_course import MigratedCourse
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
EDX_API_KEY = ACCESS_TOKEN = 'edx'
EXPIRES = datetime.datetime(year=1985, month=10, day=26, hour=1, minute=20, tzinfo=pytz.utc)
EXPIRES_STRING = EXPIRES.strftime(ISO_8601_FORMAT)

LOGGER_NAME = 'ecommerce.extensions.catalogue.management.commands.migrate_course'
logger = logging.getLogger(__name__)

Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class CourseMigrationTestMixin(CourseCatalogTestMixin):
    course_id = 'aaa/bbb/ccc'
    course_name = 'A Tést Côurse'
    commerce_api_url = '{}/courses/{}/'.format(settings.COMMERCE_API_URL.rstrip('/'), course_id)
    course_structure_url = urljoin(settings.LMS_URL_ROOT, 'api/course_structure/v0/courses/{}/'.format(course_id))
    enrollment_api_url = urljoin(settings.LMS_URL_ROOT, 'api/enrollment/v1/course/{}'.format(course_id))

    prices = {
        'honor': 0,
        'verified': 10,
        'no-id-professional': 100,
        'professional': 1000,
        'audit': 0,
        'credit': 0,
    }

    def _mock_lms_apis(self):
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock LMS API calls.')

        # Mock Commerce API
        body = {
            'name': self.course_name,
            'verification_deadline': EXPIRES_STRING,
        }
        httpretty.register_uri(httpretty.GET, self.commerce_api_url, body=json.dumps(body), content_type=JSON)

        # Mock Course Structure API
        body = {'name': self.course_name}
        httpretty.register_uri(httpretty.GET, self.course_structure_url, body=json.dumps(body), content_type=JSON)

        # Mock Enrollment API
        body = {
            'course_id': self.course_id,
            'course_modes': [{'slug': mode, 'min_price': price, 'expiration_datetime': EXPIRES_STRING} for
                             mode, price in self.prices.iteritems()]
        }
        httpretty.register_uri(httpretty.GET, self.enrollment_api_url, body=json.dumps(body), content_type=JSON)

    def assert_stock_record_valid(self, stock_record, seat, price):
        """ Verify the given StockRecord is configured correctly. """
        self.assertEqual(stock_record.partner, self.partner)
        self.assertEqual(stock_record.price_excl_tax, price)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.partner_sku, generate_sku(seat, self.partner))

    def assert_seat_valid(self, seat, mode):
        """ Verify the given seat is configured correctly. """
        certificate_type = Course.certificate_type_for_mode(mode)

        expected_title = 'Seat in {}'.format(self.course_name)
        if certificate_type != '':
            expected_title += ' with {} certificate'.format(certificate_type)

            if seat.attr.id_verification_required:
                expected_title += u' (and ID verification)'

        self.assertEqual(seat.title, expected_title)
        self.assertEqual(getattr(seat.attr, 'certificate_type', ''), certificate_type)
        self.assertEqual(seat.expires, EXPIRES)
        self.assertEqual(seat.attr.course_key, self.course_id)
        self.assertEqual(seat.attr.id_verification_required, Course.is_mode_verified(mode))

    def assert_course_migrated(self):
        """ Verify the course was migrated and saved to the database. """
        course = Course.objects.get(id=self.course_id)
        seats = course.seat_products

        # Verify that all modes are migrated.
        self.assertEqual(len(seats), len(self.prices))

        parent = course.products.get(structure=Product.PARENT)
        self.assertEqual(list(parent.categories.all()), [self.category])

        for seat in seats:
            mode = mode_for_seat(seat)
            logger.info('Validating objects for [%s] mode...', mode)

            stock_record = self.partner.stockrecords.get(product=seat)
            self.assert_seat_valid(seat, mode)
            self.assert_stock_record_valid(stock_record, seat, self.prices[mode])

    def assert_lms_api_headers(self, request, bearer=False):
        self.assertEqual(request.headers['Accept'], JSON)

        if bearer:
            self.assertEqual(request.headers['Authorization'], 'Bearer ' + ACCESS_TOKEN)
        else:
            self.assertEqual(request.headers['Content-Type'], JSON)
            self.assertEqual(request.headers['X-Edx-Api-Key'], EDX_API_KEY)


@override_settings(EDX_API_KEY=EDX_API_KEY)
class MigratedCourseTests(CourseMigrationTestMixin, TestCase):
    def setUp(self):
        super(MigratedCourseTests, self).setUp()
        toggle_switch('publish_course_modes_to_lms', True)

    def _migrate_course_from_lms(self):
        """ Create a new MigratedCourse and simulate the loading of data from LMS. """
        self._mock_lms_apis()
        migrated_course = MigratedCourse(self.course_id, self.partner.short_code)
        migrated_course.load_from_lms(ACCESS_TOKEN)
        return migrated_course

    @httpretty.activate
    def test_load_from_lms(self):
        """ Verify the method creates new objects based on data loaded from the LMS. """
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True
            migrated_course = self._migrate_course_from_lms()
            course = migrated_course.course

            # Verify that the migrated course was not published back to the LMS
            self.assertFalse(mock_publish.called)

        # Ensure LMS was called with the correct headers
        for request in httpretty.httpretty.latest_requests:
            self.assert_lms_api_headers(request)

        # Verify created objects match mocked data
        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in {}'.format(self.course_name))
        self.assertEqual(course.verification_deadline, EXPIRES)

        for seat in course.seat_products:
            mode = mode_for_seat(seat)
            logger.info('Validating objects for [%s] mode...', mode)

            self.assert_stock_record_valid(seat.stockrecords.first(), seat, Decimal(self.prices[mode]))

    @httpretty.activate
    def test_course_name_missing(self):
        """Verify the Course Structure API is queried if the Commerce API doesn't return a course name."""
        # Mock the Commerce API so that it does not return a name
        body = {
            'name': None,
            'verification_deadline': EXPIRES_STRING,
        }
        httpretty.register_uri(httpretty.GET, self.commerce_api_url, body=json.dumps(body), content_type=JSON)

        # Mock the Course Structure API
        httpretty.register_uri(httpretty.GET, self.course_structure_url, body='{}', content_type=JSON)

        # Try migrating the course, which should fail.
        try:
            migrated_course = MigratedCourse(self.course_id, self.partner.short_code)
            migrated_course.load_from_lms(ACCESS_TOKEN)
        except Exception as ex:  # pylint: disable=broad-except
            self.assertEqual(ex.message, 'Aborting migration. No name is available for {}.'.format(self.course_id))

        # Verify the Course Structure API was called.
        last_request = httpretty.last_request()
        self.assertEqual(last_request.path, urlparse(self.course_structure_url).path)

    @httpretty.activate
    def test_fall_back_to_course_structure(self):
        """
        Verify that migration falls back to the Course Structure API when data
        is unavailable from the Commerce API.
        """
        self._mock_lms_apis()

        body = {'detail': 'Not found'}
        httpretty.register_uri(
            httpretty.GET,
            self.commerce_api_url,
            status=404,
            body=json.dumps(body),
            content_type=JSON
        )

        migrated_course = MigratedCourse(self.course_id, self.partner.short_code)
        migrated_course.load_from_lms(ACCESS_TOKEN)
        course = migrated_course.course

        # Ensure that the LMS was called with the correct headers.
        course_structure_path = urlparse(self.course_structure_url).path
        for request in httpretty.httpretty.latest_requests:
            if request.path == course_structure_path:
                self.assert_lms_api_headers(request, bearer=True)
            else:
                self.assert_lms_api_headers(request)

        # Verify that created objects match mocked data.
        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in {}'.format(self.course_name))
        # Confirm that there is no verification deadline set for the course.
        self.assertEqual(course.verification_deadline, None)

        for seat in course.seat_products:
            mode = mode_for_seat(seat)
            self.assert_stock_record_valid(seat.stockrecords.first(), seat, Decimal(self.prices[mode]))

    @httpretty.activate
    def test_whitespace_stripped(self):
        """Verify that whitespace in course names is stripped during migration."""
        self._mock_lms_apis()

        body = {
            # Wrap the course name with whitespace
            'name': '  {}  '.format(self.course_name),
            'verification_deadline': EXPIRES_STRING,
        }
        httpretty.register_uri(httpretty.GET, self.commerce_api_url, body=json.dumps(body), content_type=JSON)

        migrated_course = MigratedCourse(self.course_id, self.partner.short_code)
        migrated_course.load_from_lms(ACCESS_TOKEN)
        course = migrated_course.course

        # Verify that whitespace has been stripped from the course name.
        self.assertEqual(course.name, self.course_name)

        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in {}'.format(self.course_name))


@override_settings(EDX_API_KEY=EDX_API_KEY)
class CommandTests(CourseMigrationTestMixin, TestCase):
    def setUp(self):
        super(CommandTests, self).setUp()
        toggle_switch('publish_course_modes_to_lms', True)

    @httpretty.activate
    def test_handle(self):
        """ Verify the management command retrieves data, but does not save it to the database. """
        initial_product_count = Product.objects.count()
        initial_stock_record_count = StockRecord.objects.count()

        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True
            call_command(
                'migrate_course', self.course_id, access_token=ACCESS_TOKEN, partner_short_code=self.partner.short_code
            )

            # Verify that the migrated course was not published back to the LMS
            self.assertFalse(mock_publish.called)

        # Ensure LMS was called with the correct headers
        for request in httpretty.httpretty.latest_requests:
            self.assert_lms_api_headers(request)

        self.assertEqual(Product.objects.count(), initial_product_count, 'No new Products should have been saved.')
        self.assertEqual(StockRecord.objects.count(), initial_stock_record_count,
                         'No new StockRecords should have been saved.')

    @httpretty.activate
    def test_handle_with_commit(self):
        """ Verify the management command retrieves data, and saves it to the database. """
        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            call_command(
                'migrate_course',
                self.course_id,
                access_token=ACCESS_TOKEN,
                commit=True,
                # `partner_short_code` is the option destination variable
                partner_short_code=self.partner.short_code
            )

            # Verify that the migrated course was published back to the LMS
            self.assertTrue(mock_publish.called)

        self.assert_course_migrated()

    @httpretty.activate
    def test_handle_with_no_partner(self):
        """ Verify the management command does not run if no partner short code is provided. """
        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            with LogCapture(LOGGER_NAME, level=logging.ERROR) as l:
                call_command(
                    'migrate_course',
                    self.course_id,
                    access_token=ACCESS_TOKEN,
                    commit=True
                )

                l.check((LOGGER_NAME, 'ERROR', 'Courses cannot be migrated without providing a partner short code.'))
                # Verify that the migrated course was published back to the LMS
                self.assertFalse(mock_publish.called)

    @httpretty.activate
    def test_handle_with_commit_false(self):
        """ Verify the management command does not save data to the database if commit is false"""
        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            call_command(
                'migrate_course',
                self.course_id,
                access_token=ACCESS_TOKEN,
                commit=False,
                partner=self.partner.short_code
            )

            # Verify that the migrated course was published back to the LMS
            self.assertFalse(mock_publish.called)

    @httpretty.activate
    def test_handle_with_false_switch(self):
        """ Verify the management command does not save data to the database if commit is false"""
        self._mock_lms_apis()
        toggle_switch('publish_course_modes_to_lms', False)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            call_command(
                'migrate_course',
                self.course_id,
                access_token=ACCESS_TOKEN,
                commit=True,
                partner=self.partner.short_code
            )

            # Verify that the migrated course was published back to the LMS
            self.assertFalse(mock_publish.called)
