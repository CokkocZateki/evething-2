# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import calendar

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Min, Sum

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8


TWO_PLACES = Decimal('0.00')

MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


@login_required
def trade(request):
    """Trade volume overview"""
    data = {
        'user': request.user,
    }
    # now = datetime.datetime.now()

    # Order information
    # orders = Order.objects.filter(corporation=corporation)
    # buy_orders = orders.filter(o_type='B')
    # sell_orders = orders.filter(o_type='S')
    # data['sell_total'] = orders.filter(o_type='S').aggregate(Sum('total_price'))['total_price__sum'] or 0
    # buy_orders = orders.filter(o_type='B')
    # data['buy_total'] = buy_orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
    # data['escrow_total'] = buy_orders.aggregate(Sum('escrow'))['escrow__sum'] or 0
    # data['net_asset_value'] = data['wallet_balance'] + data['sell_total'] + data['escrow_total']

    # Transaction stuff oh god
    characters = list(Character.objects.filter(
        apikeys__user=request.user,
        apikeys__valid=True,
        apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    ).values_list(
        'id',
        flat=True,
    ))
    transactions = Transaction.objects.filter(character_id__in=characters)

    t_check = []
    # All
    t_check.append(('[All]', 'all', transactions))

    # Campaigns
    for camp in Campaign.objects.filter(user=request.user.id):
        title = '[%s]' % (camp.title)
        t_check.append((title, camp.slug, camp.get_transactions_filter(transactions)))

    # Months
    agg = transactions.aggregate(min_date=Min('date'), max_date=Max('date'))
    if agg['min_date'] is not None:
        for year, month in reversed(_months_in_range(agg['min_date'], agg['max_date'])):
            name = '%s %s' % (MONTHS[month], year)
            urlpart = '%s-%02d' % (year, month)
            t_check.append((name, urlpart, transactions.filter(date__range=_month_range(year, month))))

    # Get data and stuff
    t_data = []
    for name, urlpart, trans in t_check:
        row = dict(
            name=name,
            urlpart=urlpart,
            buy_total=0,
            sell_total=0,
        )

        for data in trans.values('buy_transaction').annotate(Sum('total_price')):
            if data['buy_transaction'] is True:
                row['buy_total'] = data['total_price__sum']
            else:
                row['sell_total'] = data['total_price__sum']

        row['balance'] = row['sell_total'] - row['buy_total']

        t_data.append(row)

    data['transactions'] = t_data

    # Render template
    return render_page(
        'thing/trade.html',
        data,
        request,
        characters,
    )


@login_required
def trade_timeframe(request, year=None, month=None, period=None, slug=None):
    """Trade overview for a variety of timeframe types"""
    # Initialise data
    data = {
        'total_buys': 0,
        'total_sells': 0,
        'total_balance': 0,
        'total_projected_average': 0,
        'total_projected_market': 0,
    }

    # Get a QuerySet of transactions by this user
    characters = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    corporations = Corporation.get_ids_with_access(request.user, APIKey.CORP_WALLET_TRANSACTIONS_MASK)
    wallets = list(CorpWallet.objects.filter(corporation__in=corporations).values_list('account_id', flat=True))

    transactions = Transaction.objects.filter(
        Q(character__in=characters) |
        Q(corp_wallet__in=wallets)
    )

    # Year/Month
    if year and month:
        year = int(year)
        month = int(month)
        transactions = transactions.filter(date__range=_month_range(year, month))
        data['timeframe'] = '%s %s' % (MONTHS[month], year)
        data['urlpart'] = '%s-%02d' % (year, month)
    # Timeframe slug
    elif slug:
        camp = get_object_or_404(Campaign, slug=slug)
        transactions = camp.get_transactions_filter(transactions)
        data['timeframe'] = '%s (%s -> %s)' % (camp.title, camp.start_date, camp.end_date)
        data['urlpart'] = slug
    # All
    elif period:
        data['timeframe'] = 'all time'
        data['urlpart'] = 'all'

    # Fetch the aggregate transaction data
    data_set = transactions.values('buy_transaction', 'item').annotate(
        sum_quantity=Sum('quantity'),
        min_price=Min('price'),
        max_price=Max('price'),
        sum_total=Sum('total_price'),
    )

    t_map = {}
    # { buy_transaction, item, sum_quantity, min_price, max_price, sum_total }
    for row in data_set.iterator():
        item_id = int(row['item'])

        if item_id not in t_map:
            t_map[item_id] = {}

        if row['buy_transaction']:
            t_map[item_id]['buy_quantity'] = row['sum_quantity']
            t_map[item_id]['buy_minimum'] = row['min_price']
            t_map[item_id]['buy_maximum'] = row['max_price']
            t_map[item_id]['buy_total'] = row['sum_total']
            t_map[item_id]['buy_average'] = row['sum_total'] / row['sum_quantity']
        else:
            t_map[item_id]['sell_quantity'] = row['sum_quantity']
            t_map[item_id]['sell_minimum'] = row['min_price']
            t_map[item_id]['sell_maximum'] = row['max_price']
            t_map[item_id]['sell_total'] = row['sum_total']
            t_map[item_id]['sell_average'] = row['sum_total'] / row['sum_quantity']

    # fetch the items
    item_map = Item.objects.select_related().in_bulk(t_map.keys())

    # import time
    # start = time.time()

    data['items'] = []
    for item in item_map.values():
        t = t_map[item.id]
        item.t = t

        # Add missing data
        for k in ('buy_average', 'sell_average', 'buy_quantity', 'sell_quantity', 'buy_minimum', 'sell_minimum',
                  'buy_maximum', 'sell_maximum', 'buy_total', 'sell_total'):
            if k not in t:
                t[k] = 0

        if t['buy_average'] and t['sell_average']:
            t['average_profit'] = (t['sell_average'] - t['buy_average']).quantize(TWO_PLACES)
            t['average_profit_per'] = '%.1f' % (t['average_profit'] / t['buy_average'] * 100)

        t['diff'] = t['buy_quantity'] - t['sell_quantity']

        t['balance'] = t['sell_total'] - t['buy_total']

        # Projected balance
        if t['diff'] > 0:
            t['projected_average'] = (t['balance'] + (t['diff'] * t['sell_average'])).quantize(TWO_PLACES)
            t['projected_market'] = (t['balance'] + (t['diff'] * item.sell_price)).quantize(TWO_PLACES)
            t['outstanding'] = ((t['projected_average'] - t['balance']) * -1).quantize(TWO_PLACES)
            if t['outstanding'] == 0:
                t['outstanding'] = ((t['projected_market'] - t['balance']) * -1).quantize(TWO_PLACES)
        else:
            t['projected_average'] = t['balance']
            t['projected_market'] = t['balance']

        data['items'].append(item)

        # Update totals
        data['total_buys'] += t['buy_total']
        data['total_sells'] += t['sell_total']
        data['total_projected_average'] += t['projected_average']
        data['total_projected_market'] += t['projected_market']

    # Render template
    return render_page(
        'thing/trade_timeframe.html',
        data,
        request,
    )


def _months_in_range(min_date, max_date):
    """Get a range of months between min_date and max_date, inclusive"""
    months = []
    for year in range(min_date.year, max_date.year + 1):
        for month in range(1, 13):
            if year == min_date.year and month < min_date.month:
                continue
            elif year == max_date.year and month > max_date.month:
                continue
            else:
                months.append((year, month))

    return months


def _month_range(year, month):
    """Get a range of days for a year/month eg (01, 31)"""
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    return (start, end)
