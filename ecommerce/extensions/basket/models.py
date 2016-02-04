from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.basket.abstract_models import AbstractBasket
from oscar.core.loading import get_class

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
Selector = get_class('partner.strategy', 'Selector')


class Basket(AbstractBasket):
    site = models.ForeignKey('sites.Site', verbose_name=_("Site"), null=True, blank=True, default=None,
                             on_delete=models.SET_NULL)

    @property
    def order_number(self):
        return OrderNumberGenerator().order_number(self)

    @classmethod
    def get_basket(cls, user, site, new_basket=False):
        """Retrieve the basket belonging to the indicated user.

        If no such basket exists, create a new one. If multiple such baskets exist,
        merge them into one.
        """
        editable_baskets = cls.objects.filter(site=site, owner=user, status__in=Basket.editable_statuses)
        if len(editable_baskets) == 0:
            basket = cls.objects.create(site=site, owner=user)
        else:
            stale_baskets = list(editable_baskets)
            basket = stale_baskets.pop(0)
            for stale_basket in stale_baskets:
                # Don't add line quantities when merging baskets
                basket.merge(stale_basket, add_quantities=False)
            if new_basket:
                basket.delete()
                basket = cls.objects.create(site=site, owner=user)

        # Assign the appropriate strategy class to the basket
        basket.strategy = Selector().strategy(user=user)

        return basket

    def __unicode__(self):
        return _(u"{id} - {status} basket (owner: {owner}, lines: {num_lines})").format(
            id=self.id,
            status=self.status,
            owner=self.owner,
            num_lines=self.num_lines)


# noinspection PyUnresolvedReferences
from oscar.apps.basket.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position
