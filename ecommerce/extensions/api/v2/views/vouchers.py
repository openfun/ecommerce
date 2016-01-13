"""HTTP endpoints for interacting with vouchers."""
from oscar.core.loading import get_model
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet


Voucher = get_model('voucher', 'Voucher')


class VoucherViewSet(NonDestroyableModelViewSet):
    queryset = Voucher.objects.all()
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
