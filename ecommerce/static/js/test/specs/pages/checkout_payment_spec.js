define([
        'jquery',
        'underscore',
        'utils/utils',
        'pages/checkout_payment'
    ],
    function ($,
              _,
              Utils,
              CheckoutPayment) {
        'use strict';

        describe('Checkout Payment Page', function () {
            var data,
                form;

            beforeEach(function () {
                data = {
                    payment_page_url: 'http://www.dummy-url.com/',
                    payment_form_data: {
                        type: 'Dummy Type',
                        model: '500',
                        color: 'white'
                    }
                };

                form = $('<form>', {
                    action: data.payment_page_url,
                    method: 'POST',
                    'accept-method': 'UTF-8'
                });
            });

            describe('appendToForm', function () {
                it('should append input data to form', function () {
                    _.each(data.payment_form_data, function(value, key) {
                        CheckoutPayment.appendToForm(value, key, form);
                    });
                    expect(form.children().length).toEqual(3);
                });
            });


            describe('onDone', function () {
                it('should fill form inputs for each data key/value pair', function () {
                    spyOn(_, 'each');
                    CheckoutPayment.onDone(data);
                    expect(_.each.calls.count()).toEqual(1);
                    expect($('input').length).toEqual(3);
                });
            });

            describe('onFail', function () {
                it('should report error to message div element', function () {
                    $('<div id="messages"></div>').appendTo('body');
                    var error_messages_div = $('#messages');
                    CheckoutPayment.onFail();
                    expect(error_messages_div.text()).toEqual(
                        'Problem occurred during checkout. Please contact support'
                    );
                });
            });

            describe('onReady', function () {
                it('should disable payment button before making ajax call', function () {
                    $('<div class="payment-buttons"><button class="payment-button">Pay</button></div>')
                        .appendTo('body');
                    spyOn(Utils, 'disableElementWhileRunning');
                    CheckoutPayment.onReady();
                    $('button.payment-button').trigger('click');
                    expect(Utils.disableElementWhileRunning).toHaveBeenCalled();
                });
            });
        });
    }
);
