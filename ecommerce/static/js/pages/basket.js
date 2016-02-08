/**
 * Basket page scripts.
 **/

define([
        'jquery'
    ],
    function ($) {
        'use strict';

        var showVoucherForm = function() {
            $('#voucher_form_container').show();
            $('#voucher_form_link').hide();
            $('#id_code').focus();
        },
        hideVoucherForm = function() {
            $('#voucher_form_container').hide();
            $('#voucher_form_link').show();
        },
        onReady = function() {
            $('#voucher_form_link a').on('click', function(event) {
                event.preventDefault();
                showVoucherForm();
            });

            $('#voucher_form_cancel').on('click', function(event) {
                event.preventDefault();
                hideVoucherForm();
            });
        };

        $(document).ready(onReady);

        return {
            showVoucherForm: showVoucherForm,
            hideVoucherForm: hideVoucherForm,
            onReady: onReady
        };
    }
);
