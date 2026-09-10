# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = 'stock.lot'

    expiry_alert_status = fields.Selection(
        [
            ('normal', 'Normal'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
            ('expired', 'Expired'),
        ],
        string='Expiry Alert Status',
        compute='_compute_expiry_alert_status',
        store=True,
        index=True,
    )

    expiry_days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_expiry_alert_status',
        store=True,
    )

    expiry_alert_enabled = fields.Boolean(
        string='Expiry Alert Enabled',
        compute='_compute_expiry_alert_status',
        store=True,
    )

    expiry_stock_quantity = fields.Float(
        string='Quantity',
        compute='_compute_expiry_stock_info',
        help='Current on-hand quantity for this lot/serial.',
    )

    expiry_stock_location_id = fields.Many2one(
        'stock.location',
        string='Location',
        compute='_compute_expiry_stock_info',
        help='Current stock location for this lot/serial.',
    )

    expiry_value_at_risk = fields.Float(
        string='Value at Risk',
        compute='_compute_expiry_value_at_risk',
        help='Estimated inventory value at risk because of expiry.',
    )

    expiry_alert_last_notified = fields.Datetime(
        string='Last Alert Sent',
        readonly=True,
    )

    expiry_alert_notification_count = fields.Integer(
        string='Notification Count',
        default=0,
        readonly=True,
    )

    @api.depends(
        'expiration_date',
        'product_id',
    )
    def _compute_expiry_alert_status(self):
        today = fields.Date.context_today(self)
        Config = self.env['ms.stock.expiry.config']

        config = Config.get_active_config()

        for lot in self:
            lot.expiry_alert_status = 'normal'
            lot.expiry_days_remaining = 0
            lot.expiry_alert_enabled = False

            if not lot.expiration_date:
                continue

            expiry_date = fields.Datetime.to_datetime(
                lot.expiration_date
            ).date()

            days_remaining = (expiry_date - today).days
            lot.expiry_days_remaining = days_remaining

            if not config:
                continue

            lot.expiry_alert_enabled = True

            if days_remaining < 0:
                if config.include_expired_lots:
                    lot.expiry_alert_status = 'expired'

            elif days_remaining <= config.critical_threshold:
                lot.expiry_alert_status = 'critical'

            elif days_remaining <= config.alert_threshold:
                lot.expiry_alert_status = 'warning'

    @api.depends(
        'product_id',
    )
    def _compute_expiry_stock_info(self):
        Quant = self.env['stock.quant']

        for lot in self:
            quants = Quant.search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
            ])

            lot.expiry_stock_quantity = sum(
                quants.mapped('quantity')
            )

            location = self.env['stock.location']

            if quants:
                main_quant = max(
                    quants,
                    key=lambda q: q.quantity or 0.0
                )
                location = main_quant.location_id

            lot.expiry_stock_location_id = location

    @api.depends(
        'product_id',
    )
    def _compute_expiry_value_at_risk(self):
        Quant = self.env['stock.quant']

        for lot in self:
            quants = Quant.search([
                ('lot_id', '=', lot.id),
                ('quantity', '>', 0),
            ])

            quantity = sum(
                quants.mapped('quantity')
            )

            unit_cost = lot.product_id.standard_price or 0.0

            lot.expiry_value_at_risk = quantity * unit_cost

    def action_notify_expiry(self):
        self.ensure_one()

        if not self.expiration_date:
            raise UserError(
                _(
                    'This lot/serial number does not have '
                    'an expiry date.'
                )
            )

        config = self.env[
            'ms.stock.expiry.config'
        ].get_active_config()

        if not config:
            raise UserError(
                _(
                    'No active Stock Expiry Alert '
                    'configuration was found.'
                )
            )

        if self.expiry_alert_status == 'normal':
            raise UserError(
                _(
                    'This lot is not currently within the '
                    'configured expiry alert threshold.'
                )
            )

        recipients = config._get_recipient_emails()
        if not recipients:
            raise UserError(
                _(
                    'No recipient email configured in Stock Expiry Alert Configuration. '
                    'Please add recipients before sending notifications.'
                )
            )

        sent = config.send_lot_expiry_notification(self)
        if not sent:
            raise UserError(
                _(
                    'Failed to send notification. Please check mail template and recipients configuration.'
                )
            )

        self.write({
            'expiry_alert_last_notified': fields.Datetime.now(),
            'expiry_alert_notification_count':
                self.expiry_alert_notification_count + 1,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Notification Sent'),
                'message': _('Expiry notification sent successfully.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def get_expiry_dashboard_kpis(self):

        domain_base = [('expiration_date', '!=', False)]
        
        alert_lots = self.search(domain_base + [('expiry_alert_status', 'in', ['warning', 'critical', 'expired'])])
        
        critical_lots = alert_lots.filtered(lambda l: l.expiry_alert_status == 'critical')
        expired_lots = alert_lots.filtered(lambda l: l.expiry_alert_status == 'expired')
        
        total_val_at_risk = sum(alert_lots.mapped('expiry_value_at_risk'))

        return {
            'within_threshold': len(alert_lots),
            'critical': len(critical_lots),
            'expired': len(expired_lots),
            'value_at_risk': total_val_at_risk,
        }

    @api.model
    def get_expiry_dashboard_lots(self):
        domain = [
            ('expiration_date', '!=', False),
            ('expiry_alert_status', 'in', [
                'warning',
                'critical',
                'expired',
            ]),
        ]

        lots = self.search(
            domain,
            order='expiration_date asc',
            limit=50,
        )

        status_labels = {
            'warning': 'Warning',
            'critical': 'Critical',
            'expired': 'Expired',
        }

        result = []

        for lot in lots:
            result.append({
                'id': lot.id,
                'product': lot.product_id.display_name or '-',
                'lot_name': lot.name or '-',
                'quantity': lot.expiry_stock_quantity,
                'location': (
                    lot.expiry_stock_location_id.display_name
                    if lot.expiry_stock_location_id
                    else '-'
                ),
                'expiration_date': (
                    fields.Datetime.to_datetime(
                        lot.expiration_date
                    ).strftime('%d %b %Y')
                    if lot.expiration_date
                    else '-'
                ),
                'days_remaining': lot.expiry_days_remaining,
                'status': lot.expiry_alert_status,
                'status_label': status_labels.get(
                    lot.expiry_alert_status,
                    lot.expiry_alert_status.title()
                ),
                'value_at_risk': lot.expiry_value_at_risk,
            })

        return result