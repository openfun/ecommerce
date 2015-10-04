from django import forms


class PaymentForm(forms.Form):
    # TODO Validate the payment processor value
    payment_processor = forms.CharField()
