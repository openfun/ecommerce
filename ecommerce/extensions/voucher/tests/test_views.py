from django.test import RequestFactory
from oscar.core.loading import get_model

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.test.factories import create_coupon
from ecommerce.extensions.voucher.views import CouponReportCSVView
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


class CouponReportCSVViewTest(CourseCatalogTestMixin, TestCase):
    """Unit tests for getting coupon report."""

    def setUp(self):
        super(CouponReportCSVViewTest, self).setUp()

        self.user = self.create_user(full_name="Test User", is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory()
        self.verified_seat = self.course.create_or_update_seat('verified', False, 0, self.partner)

        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()

        partner1 = PartnerFactory(name='Tester1')
        catalog1 = Catalog.objects.create(name="Test catalog 1", partner=partner1)
        catalog1.stock_records.add(self.stock_record)
        self.coupon1 = create_coupon(partner=partner1, catalog=catalog1)
        self.coupon1.history.all().update(history_user=self.user)
        partner2 = PartnerFactory(name='Tester2')
        catalog2 = Catalog.objects.create(name="Test catalog 2", partner=partner2)
        catalog2.stock_records.add(self.stock_record)
        self.coupon2 = create_coupon(partner=partner2, catalog=catalog2)
        self.coupon2.history.all().update(history_user=self.user)

    def request_specific_voucher_report(self, coupon_id):
        request = RequestFactory()
        response = CouponReportCSVView().get(request, coupon_id=coupon_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 6)

    def test_get_csv_report_for_specific_coupon(self):
        """
        Test the get method.
        CSV voucher report should contain coupon specific voucher data.
        """
        self.request_specific_voucher_report(self.coupon1.id)
        self.request_specific_voucher_report(self.coupon2.id)
