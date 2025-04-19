odoo.define('pos_open_cashdrawer.OpenDrawer', function (require) {
    'use strict';
    const { Gui } = require('point_of_sale.Gui');
    const PosComponent = require('point_of_sale.PosComponent');
    const { identifyError } = require('point_of_sale.utils');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const { useListener } = require("@web/core/utils/hooks");
    const Registries = require('point_of_sale.Registries');
    const PaymentScreen = require('point_of_sale.PaymentScreen');

    class OpenCashDrawer extends PosComponent {
        setup() {
            super.setup();
            useListener('click', this.onClick);
        }

        async onClick() {
            const { confirmed } = await this.showPopup("ConfirmPopup", {
                title: this.env._t('Open Cash Drawer ?'),
                body: this.env._t('Are you sure you want to Open Cash Drawer ?'),
            });

            if (confirmed) {
                this.sendGetRequest();
            }
        }

        sendGetRequest() {
            console.log('PosComponent:', PosComponent);
            console.log('ProductScreen:', ProductScreen);
            console.log('Registries:', Registries);
            console.log('PaymentScreen:', PaymentScreen);
            const url = 'https://localhost:8443/open_cash_drawer';

            const requestOptions = {
                method: 'GET',
                mode: 'no-cors',
                headers: {
                    'Content-Type': 'application/json',
                },
            };

            fetch(url, requestOptions)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Success:', data);
                })
                .catch(error => {
                    console.error('Error:', error);
                });
        }
    }

    OpenCashDrawer.template = 'OpenCashDrawer';
    ProductScreen.addControlButton({
        component: OpenCashDrawer,
        condition: function () {
            return this.env.pos;
        },
    });
    Registries.Component.add(OpenCashDrawer);
    return OpenCashDrawer;
});