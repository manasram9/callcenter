from odoo import fields, http, _, tools
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import \
    CustomerPortal, pager as portal_pager, get_records_pager
from collections import OrderedDict
import json, base64
from dateutil.parser import parse
from operator import itemgetter
from odoo.tools import groupby as groupbyelem
from odoo.osv.expression import OR
import datetime
import pytz
from datetime import timedelta
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.website_form.controllers.main import WebsiteForm


class HelpdeskController_inherit(WebsiteForm):

    def insert_record(self, request, model, values, custom, meta=None):
        if values.get('helpdesk_portal_id'):
            model_name = model.sudo().model
            ticket_id = request.env[model_name].sudo().with_context(mail_create_nosubscribe=True).browse(
                values.get('helpdesk_portal_id'))
            if ticket_id:
                ticket_id.write(values)
                if custom or meta:
                    default_field = model.website_form_default_field_id
                    default_field_data = values.get(default_field.name, '')
                    custom_content = (default_field_data + "\n\n" if default_field_data else '') \
                                     + (self._custom_label + custom + "\n\n" if custom else '') \
                                     + (self._meta_label + meta if meta else '')

                    # If there is a default field configured for this model, use it.
                    # If there isn't, put the custom data in a message instead
                    if default_field.name:
                        if default_field.ttype == 'html' or model_name == 'mail.mail':
                            custom_content = nl2br(custom_content)
                        ticket_id.update({default_field.name: custom_content})
                    else:
                        values = {
                            'body': nl2br(custom_content),
                            'model': model_name,
                            'message_type': 'comment',
                            'no_auto_thread': False,
                            'res_id': ticket_id.id,
                        }
                        mail_id = request.env['mail.message'].sudo().create(values)
                return ticket_id.id
        return super(HelpdeskController_inherit, self).insert_record(request, model, values, custom, meta)


class Helpdesk_ticket_portal(CustomerPortal):

    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth="user", website=True)
    def my_helpdesk_tickets(self, page=1, date_begin=None, date_end=None, sortby=None, search=None, search_in='content',
                            **kw):
        values = self._prepare_portal_layout_values()
        user = request.env.user
        domain = []

        searchbar_sortings = {
            'date_desc': {'label': _('Created Date Desc'), 'order': 'create_date desc, id desc'},
            'date_asc': {'label': _('Created Date Asc'), 'order': 'create_date asc, id asc'},
            'open_day_asc': {'label': _('Open Days Asc'), 'order': 'x_studio_opendays asc, id asc'},
            'open_day_desc': {'label': _('Open Days Desc'), 'order': 'x_studio_opendays desc, id desc'}
        }
        searchbar_inputs = {
            'content': {'input': 'content', 'label': _('Search <span class="nolabel"> (in Content)</span>')},
            'message': {'input': 'message', 'label': _('Search in Messages')},
            'customer': {'input': 'customer', 'label': _('Search in Customer')},
            'id': {'input': 'id', 'label': _('Search ID')},
            'all': {'input': 'all', 'label': _('Search in All')},
        }

        # default sort by value
        if not sortby:
            sortby = 'date_desc'
        order = searchbar_sortings[sortby]['order']

        # archive groups - Default Group By 'create_date'
        archive_groups = self._get_archive_groups('helpdesk.ticket', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        # search
        if search and search_in:
            search_domain = []
            if search_in in ('id', 'all'):
                search_domain = OR([search_domain, [('id', 'ilike', search)]])
            if search_in in ('content', 'all'):
                search_domain = OR([search_domain, ['|', ('name', 'ilike', search), ('description', 'ilike', search)]])
            if search_in in ('customer', 'all'):
                search_domain = OR([search_domain, [('partner_id', 'ilike', search)]])
            if search_in in ('message', 'all'):
                search_domain = OR([search_domain, [('message_ids.body', 'ilike', search)]])
            domain += search_domain

        # pager
        tickets_count = request.env['helpdesk.ticket'].search_count(domain)
        pager = portal_pager(
            url="/my/tickets",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=tickets_count,
            page=page,
            step=self._items_per_page
        )

        tickets = request.env['helpdesk.ticket'].search(domain, order=order, limit=self._items_per_page,
                                                        offset=pager['offset'])
        request.session['my_tickets_history'] = tickets.ids[:100]

        values.update({
            'date': date_begin,
            'tickets': tickets,
            'page_name': 'ticket',
            'default_url': '/my/tickets',
            'pager': pager,
            'archive_groups': archive_groups,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'sortby': sortby,
            'search_in': search_in,
            'search': search,
        })
        return request.render("helpdesk.portal_helpdesk_ticket", values)

    @http.route(['/my/ticket/create', '/my/ticket/contact/search/<int:contact_id>'], type='http', auth='user',
                website=True)
    def portal_ticket_create(self, contact_id=None, values={}, default_values={}, **kw):
        is_asc = False
        if request.env.user.has_group('ki_helpdesk_extend.group_asc_portal_access'):
            is_asc = True
        ticket_type_ids = request.env['helpdesk.ticket.type'].sudo().search_read([], ['id', 'name'])
        modal_name_dic = dict(request.env['helpdesk.ticket']._fields['x_studio_model_name'].selection)
        new_modal_list = [{
            'id': i,
            'name': k
        } for i, k in modal_name_dic.items()]
        values.update({
            'default_values': default_values,
            'is_asc': is_asc,
            'ticket_type_ids': ticket_type_ids,
            'new_modal_list': new_modal_list
        })
        if is_asc:
            teams = request.env['helpdesk.team'].sudo().search_read([('use_website_helpdesk_form', '=', True)],
                                                                    ['id', 'name', 'member_ids'])
            users = request.env['res.users'].sudo().search_read(
                [('groups_id', 'in', request.env.ref('helpdesk.group_helpdesk_user').id)],
                ['id', 'name'])
            values.update({
                'teams': teams,
                'users': users
            })

            if contact_id:
                email = kw.get('email')
                res_contact_id = request.env['res.partner'].sudo().search([('email', '=', email)])
                if res_contact_id:
                    default_values['partner_name'] = res_contact_id.name
                    default_values['email'] = res_contact_id.email
                    default_values['x_studio_field_w3gK7'] = res_contact_id.phone or res_contact_id.mobile
                else:
                    default_values['partner_name'] = ''
                    default_values['email'] = kw.get('email')
                    default_values['x_studio_field_w3gK7'] = ''

                    values.update({
                        'create_contact': True,
                        'no_record': True
                    })
            else:
                default_values['partner_name'] = ''
                default_values['email'] = ''
                default_values['x_studio_field_w3gK7'] = ''

        if request.env.user.partner_id != request.env.ref('base.public_partner') and not is_asc:
            default_values['partner_name'] = request.env.user.partner_id.name
            default_values['email'] = request.env.user.partner_id.email
            default_values[
                'x_studio_field_w3gK7'] = request.env.user.partner_id.phone or request.env.user.partner_id.phone

        response = request.render("ki_helpdesk_extend.helpdesk_portal_create_ticket", values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @http.route(['/my/ticket/edit/<int:ticket_id>'], type='http', auth='user',
                website=True)
    def portal_ticket_edit(self, ticket_id=None, **kw):
        values = {}
        default_values = {}
        is_asc = False
        modal_name_dic = dict(request.env['helpdesk.ticket']._fields['x_studio_model_name'].selection)
        new_modal_list = [{
            'id': i,
            'name': k
        } for i, k in modal_name_dic.items()]
        if request.env.user.has_group('ki_helpdesk_extend.group_asc_portal_access'):
            is_asc = True
        values.update({
            'default_values': default_values,
            'is_asc': is_asc,
        })
        ticket_id = request.env['helpdesk.ticket'].browse(ticket_id)
        if ticket_id:
            default_values.update({
                'id': ticket_id.id,
                'partner_name': ticket_id.name,
                'email': ticket_id.email,
                'x_studio_field_w3gK7': ticket_id.x_studio_field_w3gK7,
                'x_studio_model_name': ticket_id.x_studio_model_name,
                'x_studio_serial_no': ticket_id.x_studio_serial_no,
                'name': ticket_id.name,
                'description': ticket_id.description,
                'team_id': ticket_id.team_id.id,
                'user_id': ticket_id.user_id.id,
                'ticket_type_id': ticket_id.ticket_type_id.id
            })
        if is_asc:
            teams = request.env['helpdesk.team'].sudo().search_read([('use_website_helpdesk_form', '=', True)],
                                                                    ['id', 'name'])
            users = request.env['res.users'].sudo().search_read(
                [('groups_id', 'in', request.env.ref('helpdesk.group_helpdesk_user').id)],
                ['id', 'name'])
            values.update({
                'teams': teams,
                'users': users,
            })
        ticket_type_ids = request.env['helpdesk.ticket.type'].sudo().search_read([], ['id', 'name'])
        values.update({
            'default_values': default_values,
            'ticket_type_ids': ticket_type_ids,
            'new_modal_list': new_modal_list
        })
        response = request.render("ki_helpdesk_extend.helpdesk_portal_edit_ticket", values)
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    def _ticket_get_page_view_values(self, ticket, access_token, **kwargs):
        call_super = super(Helpdesk_ticket_portal, self)._ticket_get_page_view_values(ticket, access_token, **kwargs)
        if call_super.get('page_name', '') == 'ticket':
            ticket_id = call_super.get('ticket')
            if len(ticket_id.ids) == 1:
                stage_ids = request.env['helpdesk.stage'].sudo().search([('team_ids', '=', ticket_id.team_id.id)])
                call_super['stage_ids'] = stage_ids
        return call_super

    @http.route(['/ticket/stage/<int:ticket_id>/<int:stage_id>'], type='http', auth='user', website=True)
    def ticket_stage_change(self, ticket_id, stage_id=None, **kw):
        ticket_id = request.env['helpdesk.ticket'].browse(ticket_id)
        url = '/'
        if ticket_id and stage_id:
            ticket_id.sudo().write({
                'stage_id': stage_id
            })
            url = '/my/ticket/' + str(ticket_id.id)
        return request.redirect(url)

    @http.route('/ticket/helpdesk_team/validate', type='json', auth='user')
    def ticket_helpdeskteam_validate(self, **kw):
        team_id = kw.get('team_id')
        if team_id:
            help_team_id = request.env['helpdesk.team'].sudo().search(
                [('id', '=', team_id), ('use_website_helpdesk_form', '=', True)])
            if help_team_id:
                users_id = []
                members = help_team_id.member_ids or help_team_id.member_ids.search([('groups_id', 'in', request.env.ref('helpdesk.group_helpdesk_user').id)])
                for user in members:
                    users_id.append({'id': user.id, 'name': user.name})
                return users_id
            return False
        return 'error'
