from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockExpiryAlertConfig(models.Model):
    _name = 'ms.stock.expiry.config'
    _description = 'Stock Expiry Alert Configuration'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(
        string='Configuration Name',
        required=True,
        default='Stock Expiry Alert Configuration',
        tracking=True,
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )

    alert_threshold = fields.Integer(
        string='Alert Threshold (Days)',
        required=True,
        default=30,
        tracking=True,
        help=(
            'Lots/serials expiring within this number of days '
            'will appear in the expiry alert list.'
        ),
    )

    critical_threshold = fields.Integer(
        string='Critical Threshold (Days)',
        required=True,
        default=7,
        tracking=True,
        help=(
            'Lots/serials with this many or fewer days remaining '
            'will be marked as Critical.'
        ),
    )

    check_frequency = fields.Selection(
        [
            ('daily', 'Daily'),
            ('twice_daily', 'Twice Daily'),
            ('weekly', 'Weekly'),
        ],
        string='Check Frequency',
        required=True,
        default='daily',
        tracking=True,
    )

    check_time = fields.Float(
        string='Check Time',
        default=6.0,
        tracking=True,
        help='Time of day when the expiry check should run.',
    )

    recipient_ids = fields.Many2many(
        'res.users',
        'ms_stock_expiry_config_user_rel',
        'config_id',
        'user_id',
        string='Recipients',
        tracking=True,
        help='Users who should receive expiry notifications.',
    )

    recipient_partner_ids = fields.Many2many(
        'res.partner',
        'ms_stock_expiry_config_partner_rel',
        'config_id',
        'partner_id',
        string='Email Recipients',
        tracking=True,
        help='Additional email recipients for expiry notifications.',
    )

    delivery_daily_digest = fields.Boolean(
        string='Daily Digest',
        default=True,
        tracking=True,
        help='Send a daily summary of expiring lots.',
    )

    delivery_immediate_critical = fields.Boolean(
        string='Immediately (Critical Only)',
        default=True,
        tracking=True,
        help='Send an immediate email when a lot becomes Critical.',
    )

    warehouse_ids = fields.Many2many(
        'stock.warehouse',
        'ms_stock_expiry_config_warehouse_rel',
        'config_id',
        'warehouse_id',
        string='Warehouses Included',
        tracking=True,
        help='Leave empty to monitor all warehouses.',
    )

    all_warehouses = fields.Boolean(
        string='All Warehouses',
        default=True,
        tracking=True,
    )

    category_ids = fields.Many2many(
        'product.category',
        'ms_stock_expiry_config_category_rel',
        'config_id',
        'category_id',
        string='Product Categories',
        tracking=True,
        help='Leave empty to monitor all product categories.',
    )

    category_scope = fields.Selection(
        [
            ('all', 'All categories with expiry tracking enabled'),
            ('selected', 'Selected Categories Only'),
        ],
        string='Product Categories',
        default='all',
        required=True,
        tracking=True,
    )

    include_expired_lots = fields.Selection(
        [
            ('yes', 'Yes, flag separately'),
            ('no', 'No'),
        ],
        string='Include Already-Expired Lots',
        default='yes',
        required=True,
        tracking=True,
        help='Include expired lots in the alert list and digest.',
    )

    last_check_datetime = fields.Datetime(
        string='Last Check',
        readonly=True,
        tracking=True,
    )

    last_digest_datetime = fields.Datetime(
        string='Last Digest',
        readonly=True,
        tracking=True,
    )

    @api.constrains('alert_threshold', 'critical_threshold')
    def _check_thresholds(self):
        for record in self:
            if record.alert_threshold < 0:
                raise ValidationError(
                    _("Alert Threshold cannot be negative.")
                )

            if record.critical_threshold < 0:
                raise ValidationError(
                    _("Critical Threshold cannot be negative.")
                )

            if record.critical_threshold > record.alert_threshold:
                raise ValidationError(
                    _(
                        "Critical Threshold must be less than or equal "
                        "to Alert Threshold."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('active', True):
                active_configs = self.search([
                    ('active', '=', True),
                ])

                if active_configs:
                    active_configs.write({
                        'active': False,
                    })

                break

        return super().create(vals_list)


    def write(self, vals):
        if vals.get('active') is True:
            active_configs = self.search([
                ('active', '=', True),
                ('id', 'not in', self.ids),
            ])

            if active_configs:
                active_configs.write({
                    'active': False,
                })

        return super().write(vals)
                
                
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get('include_expired_lots') not in ['yes', 'no']:
            res['include_expired_lots'] = 'yes'
        return res

    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % (self.name or '')
        default['active'] = False

        if default.get('include_expired_lots') not in ['yes', 'no']:
            default['include_expired_lots'] = self.include_expired_lots if self.include_expired_lots in ['yes', 'no'] else 'yes'

        return super().copy(default)
    
    @api.model
    def get_active_config(self):
        return self.search(
            [('active', '=', True)],
            order='id desc',
            limit=1,
        )

    def _check_active_for_manual_action(self):
        self.ensure_one()

        if self.active:
            return True

        active_config = self.get_active_config()

        if active_config:
            raise ValidationError(
                _(
                    "This configuration is inactive. "
                    "The active configuration is '%s'. "
                    "Please activate this configuration before running "
                    "the action."
                ) % active_config.name
            )

        raise ValidationError(
            _(
                "This configuration is inactive. "
                "Please activate this configuration before running "
                "the action."
            )
        )

    def _get_monitored_lots(self):
        self.ensure_one()

        domain = [
            ('expiration_date', '!=', False),
            ('product_id', '!=', False),
        ]

        if self.include_expired_lots == 'no':
            domain.append(
                ('expiration_date', '>=', fields.Datetime.now())
            )

        lots = self.env['stock.lot'].search(domain)

        today = fields.Date.context_today(self)
        alert_date = today + timedelta(days=self.alert_threshold)

        filtered_lots = self.env['stock.lot']

        for lot in lots:
            if not lot.expiration_date:
                continue

            expiry_date = fields.Datetime.to_datetime(
                lot.expiration_date
            ).date()

            if expiry_date > alert_date and expiry_date >= today:
                continue

            if self.category_scope == 'selected' and self.category_ids:
                if lot.product_id.categ_id not in self.category_ids:
                    continue

            if not self.all_warehouses and self.warehouse_ids:
                warehouse = self._get_lot_warehouse(lot)

                if warehouse and warehouse not in self.warehouse_ids:
                    continue

            filtered_lots |= lot

        return filtered_lots

    def _get_lot_warehouse(self, lot):

        quant_domain = [
            ('lot_id', '=', lot.id),
            ('quantity', '>', 0),
        ]

        quants = self.env['stock.quant'].search(
            quant_domain
        )

        if not quants:
            return self.env['stock.warehouse']

        warehouse_model = self.env['stock.warehouse']

        for quant in quants:
            location = quant.location_id

            warehouse = warehouse_model.search(
                [
                    '|',
                    ('lot_stock_id', '=', location.id),
                    (
                        'view_location_id',
                        'parent_of',
                        location.id,
                    ),
                ],
                limit=1,
            )

            if warehouse:
                return warehouse

        return self.env['stock.warehouse']

    def send_lot_expiry_notification(self, lot):
        self.ensure_one()

        template = self.env.ref(
            'ms_stock_expiry_alert.mail_template_expiry_alert',
            raise_if_not_found=False,
        )

        if not template:
            return False

        recipients = self._get_recipient_emails()
        
        if not recipients:
            return False

        email_values = {}

        template.send_mail(
            lot.id,
            force_send=True,
            email_values=email_values,
        )

        body_html = template._render_field('body_html', [lot.id])[lot.id]

        lot.message_post(
            body=body_html,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return True

    def _get_recipient_emails(self):
        self.ensure_one()

        emails = set()

        for user in self.recipient_ids:
            if user.email:
                emails.add(user.email)

        for partner in self.recipient_partner_ids:
            if partner.email:
                emails.add(partner.email)

        return list(emails)

    def _should_run_now(self):
        self.ensure_one()
        if not self.last_check_datetime:
            return True

        now = fields.Datetime.now()
        diff = now - self.last_check_datetime

        if self.check_frequency == 'daily' and diff.total_seconds() < 86400:
            return False
        elif self.check_frequency == 'twice_daily' and diff.total_seconds() < 43200:
            return False
        elif self.check_frequency == 'weekly' and diff.days < 7:
            return False

        return True
    
    @api.model
    def cron_check_expiry(self):

        configs = self.search([
            ('active', '=', True),
        ])

        for config in configs:
            if not config._should_run_now():
                continue

            lots = config._get_monitored_lots()

            for lot in lots:
                status = lot.expiry_alert_status

                if status == 'critical':
                    if config.delivery_immediate_critical:
                        config.send_lot_expiry_notification(lot)

                        lot.write({
                            'expiry_alert_last_notified':
                                fields.Datetime.now(),
                            'expiry_alert_notification_count':
                                lot.expiry_alert_notification_count + 1,
                        })

            config.write({
                'last_check_datetime': fields.Datetime.now(),
            })

        return True

    @api.model
    def cron_send_daily_digest(self):

        configs = self.search([
            ('active', '=', True),
            ('delivery_daily_digest', '=', True),
        ])

        for config in configs:
            lots = config._get_monitored_lots()

            if not lots:
                config.write({
                    'last_digest_datetime': fields.Datetime.now(),
                })
                continue

            template = self.env.ref(
                'ms_stock_expiry_alert.mail_template_expiry_digest',
                raise_if_not_found=False,
            )

            if not template:
                continue

            recipients = config._get_recipient_emails()
            if not recipients:
                config.write({
                    'last_digest_datetime': fields.Datetime.now(),
                })
                continue

            email_values = {}

            if recipients:
                email_values['email_to'] = ','.join(recipients)

            template.with_context(
                expiry_lot_ids=lots.ids,
            ).send_mail(
                config.id,
                force_send=True,
                email_values=email_values,
            )

            config.write({
                'last_digest_datetime': fields.Datetime.now(),
            })

        return True

    def action_run_expiry_check(self):
        self.ensure_one()
        self._check_active_for_manual_action()
        self.cron_check_expiry()

        self.write({
            'last_check_datetime': fields.Datetime.now()
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Expiry Check Completed'),
                'message': _(
                    'The stock expiry check has been completed successfully.'
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },
            },
        }

    def action_send_daily_digest(self):
        self.ensure_one()
        self._check_active_for_manual_action()
        
        if not self.delivery_daily_digest:
            raise ValidationError(
                _(
                    'Daily Digest is disabled for this configuration. '
                    'Please enable it before sending the digest.'
                )
            )

        self.cron_send_daily_digest()

        self.write({
            'last_digest_datetime': fields.Datetime.now()
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Expiry Digest'),
                'message': _(
                    'The expiry digest has been sent successfully.'
                ),
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },
            },
        }