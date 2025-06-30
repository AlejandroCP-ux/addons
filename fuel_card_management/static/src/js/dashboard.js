odoo.define('fuel_card_management.dashboard', function (require) {
    "use strict";

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var rpc = require('web.rpc');
    var session = require('web.session');

    var QWeb = core.qweb;

    var FuelCardDashboard = AbstractAction.extend({
        template: 'FuelCardDashboard',
        events: {
            'click .o_dashboard_action': '_onDashboardActionClick',
        },

        init: function(parent, context) {
            this._super(parent, context);
            this.dashboardData = {};
        },

        willStart: function() {
            var self = this;
            return this._super().then(function() {
                return self._fetchDashboardData();
            });
        },

        _fetchDashboardData: function() {
            var self = this;
            return rpc.query({
                model: 'fuel.magnetic.card',
                method: 'get_dashboard_data',
                args: [],
            }).then(function(result) {
                self.dashboardData = result;
            });
        },

        _onDashboardActionClick: function(ev) {
            ev.preventDefault();
            var action = $(ev.currentTarget).data('action');
            
            switch(action) {
                case 'cards':
                    this.do_action({
                        name: 'Tarjetas Magnéticas',
                        res_model: 'fuel.magnetic.card',
                        type: 'ir.actions.act_window',
                        views: [[false, 'list'], [false, 'form']],
                        target: 'current',
                    });
                    break;
                case 'tickets':
                    this.do_action({
                        name: 'Tickets de Combustible',
                        res_model: 'fuel.ticket',
                        type: 'ir.actions.act_window',
                        views: [[false, 'list'], [false, 'form']],
                        target: 'current',
                    });
                    break;
                case 'plans':
                    this.do_action({
                        name: 'Planes de Combustible',
                        res_model: 'fuel.plan',
                        type: 'ir.actions.act_window',
                        views: [[false, 'list'], [false, 'form']],
                        target: 'current',
                    });
                    break;
                case 'pending_plans':
                    this.do_action({
                        name: 'Planes Pendientes de Aprobación',
                        res_model: 'fuel.plan',
                        type: 'ir.actions.act_window',
                        views: [[false, 'list'], [false, 'form']],
                        domain: [['state', '=', 'pending_approval']],
                        target: 'current',
                    });
                    break;
            }
        },
    });

    core.action_registry.add('fuel_card_dashboard', FuelCardDashboard);

    return FuelCardDashboard;
});