from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory, VoucherFactory

from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


class CouponProductTest(TestCase):
    """ Test coupon products."""

    def test_coupon_product(self):
        """Test if a coupon product is properly created."""
        coupon_product_class, _ = ProductClass.objects.get_or_create(name='coupon')
        coupon_product = ProductFactory(
            product_class=coupon_product_class,
            title='Test product'
        )
        voucher = VoucherFactory(code='MYVOUCHER')
        voucherList = CouponVouchers.objects.create(coupon=coupon_product)
        voucherList.vouchers.add(voucher)
        coupon_product.attr.coupon_voucher = voucherList

        # clean() is an Oscar validation method for products
        self.assertIsNone(coupon_product.clean())
        self.assertIsInstance(coupon_product, Product)
        self.assertEqual(coupon_product.title, 'Test product')
        self.assertEqual(coupon_product.attr.coupon_voucher.vouchers.count(), 1)
        self.assertEqual(coupon_product.attr.coupon_voucher.vouchers.first().code, 'MYVOUCHER')
