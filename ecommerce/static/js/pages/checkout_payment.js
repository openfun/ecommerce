/**
 * Checkout payment page scripts.
 **/

define([
        'jquery',
        'underscore',
        'utils/utils',
        'jquery-cookie'
    ],
    function ($,
              _,
              Utils) {
        'use strict';

        var appendToForm = function (value, key, form) {
            $('<input>').attr({
                type: 'text',
                name: key,
                value: value
            }).appendTo(form);
        },
        onDone = function (data) {
            var $form = $('<form>', {
                action: data.payment_page_url,
                method: 'POST',
                'accept-method': 'UTF-8'
            });

            _.each(data.payment_form_data, appendToForm($form));

            $form.submit();
        },
        onFail = function(){
            var message = gettext('Problem occurred during checkout. Please contact support');
            $('#messages').empty().append(
                '<div class="error">' + message + '</div>'
            );
        },
        onReady = function(){
            var $paymentButtons = $('.payment-buttons'),
                basketId = $paymentButtons.data('basket-id');

            $paymentButtons.find('.payment-button').click(function (e) {
                var $btn = $(e.target),
                    deferred = new $.Deferred(),
                    promise = deferred.promise(),
                    paymentProcessor = $btn.val(),
                    data = {
                        basket_id: basketId,
                        payment_processor: paymentProcessor
                    };

                Utils.disableElementWhileRunning($btn, function() { return promise; });

                $.ajax({
                    url: '/api/v2/checkout/',
                    type: 'POST',
                    contentType: 'application/json; charset=utf-8',
                    dataType: 'json',
                    headers: {
                        'X-CSRFToken': $.cookie('ecommerce_csrftoken')
                    },
                    data: JSON.stringify(data)
                })
                .done(onDone)
                .fail(onFail);
            });
        };

        $(document).ready(onReady);

        return {
            appendToForm: appendToForm,
            onDone: onDone,
            onFail: onFail,
            onReady: onReady
        };
    }
);
