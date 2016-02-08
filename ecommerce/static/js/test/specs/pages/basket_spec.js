define([
        'jquery',
        'underscore',
        'utils/utils',
        'pages/basket'
    ],
    function ($,
              _,
              Utils,
              Basket) {
        'use strict';

        describe('Basket Page', function () {
            beforeEach(function () {
                $('<div id="voucher_form_container"><input id="id_code">' +
                    '<a id="voucher_form_cancel"></a></button></div>'
                ).appendTo('body');
                $('<div id="voucher_form_link"><a href=""></a></div>').appendTo('body');
            });

            describe('showVoucherForm', function () {
                it('should show voucher form', function () {
                    Basket.showVoucherForm();
                    expect($('#voucher_form_container').is(':visible')).toBeTruthy();
                    expect($('#voucher_form_link').is(':visible')).toBeFalsy();
                    expect($('#id_code').is(':focus')).toBeTruthy();
                });
            });

            describe('hideVoucherForm', function () {
                it('should hide voucher form', function () {
                    Basket.showVoucherForm();
                    Basket.hideVoucherForm();
                    expect($('#voucher_form_container').is(':visible')).toBeFalsy();
                    expect($('#voucher_form_link').is(':visible')).toBeTruthy();
                });
            });

            describe('onReady', function () {
                it('should toggle voucher form on click', function () {
                    Basket.onReady();

                    $('#voucher_form_link a').trigger('click');
                    expect($('#voucher_form_container').is(':visible')).toBeTruthy();
                    expect($('#voucher_form_link').is(':visible')).toBeFalsy();
                    expect($('#id_code').is(':focus')).toBeTruthy();

                    $('#voucher_form_cancel').trigger('click');
                    expect($('#voucher_form_container').is(':visible')).toBeFalsy();
                    expect($('#voucher_form_link').is(':visible')).toBeTruthy();
                });
            });
        });
    }
);
