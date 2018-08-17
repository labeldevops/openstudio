# -*- coding: utf-8 -*-

import datetime

from gluon import *


class Reports:
    def get_query_subscriptions_new_in_month(self, date):
        """
            Returns query for new subscriptions
        """
        firstdaythismonth = datetime.date(date.year, date.month, 1)
        next_month = date.replace(day=28) + datetime.timedelta(days=4)  # this will never fail
        lastdaythismonth = next_month - datetime.timedelta(days=next_month.day)

        query = """SELECT cu.id,
                          cu.archived,
                          cu.thumbsmall,
                          cu.birthday,
                          cu.display_name,
                          cu.date_of_birth,
                          csu.school_subscriptions_id,
                          csu.startdate,
                          csu.payment_methods_id
                   FROM auth_user cu
                   LEFT JOIN
                       (SELECT auth_customer_id,
                               startdate,
                               enddate,
                               school_subscriptions_id,
                               payment_methods_id
                        FROM customers_subscriptions
                        GROUP BY auth_customer_id) csu
                   ON cu.id = csu.auth_customer_id
                   LEFT JOIN school_subscriptions ssu
                   ON ssu.id = csu.school_subscriptions_id
                   ,
                   (SELECT min(startdate) startdate,
                                          auth_customer_id
                    FROM customers_subscriptions
                    GROUP BY auth_customer_id) chk
                   WHERE chk.startdate = csu.startdate AND
                         chk.auth_customer_id = csu.auth_customer_id AND
                         csu.startdate >= '{firstdaythismonth}' AND csu.startdate <= '{lastdaythismonth}'
                   ORDER BY ssu.Name,
                            cu.display_name
                            DESC""".format(firstdaythismonth=firstdaythismonth,
                                           lastdaythismonth=lastdaythismonth)
        return query


    def get_class_revenue_summary(self, clsID, date, quick_stats=True):
        """
        :param subscription_quick_stats: Boolean - use db.school_subscriptions.QuickStatsAmount or not
        :return:
        """
        from os_class import Class

        cls = Class(clsID, date)
        class_prices = cls.get_prices()

        data = {
            'subscriptions': {},
            'classcards': {},
            'dropin': {
                'membership': {
                    'count': 0,
                    'amount': class_prices['dropin_membership']
                },
                'no_membership': {
                    'count': 0,
                    'amount': class_prices['dropin']
                }
            },
            'trial': {
                'membership': {
                    'count': 0,
                    'amount': class_prices['trial_membership']
                },
                'no_membership': {
                    'count': 0,
                    'amount': class_prices['trial']
                }
            },
            'complementary': {
                'count': 0,
                'amount': 0
            },
            'total': {
                'count': 0,
                'amount': 0
            }
        }

        rows = self.get_class_revenue_rows(clsID, date)
        for i, row in enumerate(rows):
            repr_row = list(rows[i:i + 1].render())[0]

            ex_vat = 0
            vat = 0
            in_vat = 0
            description = ''
            if row.classes_attendance.AttendanceType is None:
                # Subscription
                name = row.school_subscriptions.Name
                amount = row.school_subscriptions.QuickStatsAmount
                if data['subscriptions'].get(name, False):
                    data['subscriptions'][name]['count'] += 1
                    data['subscriptions'][name]['total'] = \
                        data['subscriptions'][name]['count'] * amount
                else:
                    data['subscriptions'][name] = {
                        'count': 1,
                        'total': amount,
                        'amount': amount
                    }

                data['total']['amount'] += amount

            elif row.classes_attendance.AttendanceType == 1:
                # Trial
                if row.classes_attendance.CustomerMembership:
                    data['trial']['membership']['count'] += 1
                    data['total']['amount'] += data['trial']['membership']['amount']
                else:
                    data['trial']['no_membership']['count'] += 1
                    data['total']['amount'] += data['trial']['no_membership']['amount']

            elif row.classes_attendance.AttendanceType == 2:
                # Dropin
                if row.classes_attendance.CustomerMembership:
                    data['dropin']['membership']['count'] += 1
                    data['total']['amount'] += data['dropin']['membership']['amount']
                else:
                    data['dropin']['no_membership']['count'] += 1
                    data['total']['amount'] += data['dropin']['no_membership']['amount']

            elif row.classes_attendance.AttendanceType == 3:
                # Class card
                name = row.school_classcards.Name
                if not row.school_classcards.Unlimited:
                    amount = row.school_classcards.Price / row.school_classcards.Classes
                else:
                    revenue = get_class_revenue_classcard(row)
                    amount = revenue['total_revenue_in_vat']
                if data['classcards'].get(name, False):
                    data['classcards'][name]['count'] += 1
                    data['classcards'][name]['total'] = \
                        data['classcards'][name]['count'] * amount
                else:
                    data['classcards'][name] = {
                        'count': 1,
                        'total': amount,
                        'amount': amount
                    }

                data['total']['amount'] += amount

            elif row.classes_attendance.AttendanceType == 4:
                # Complementary
                data['complementary']['count'] += 1

            data['total']['count'] += 1


        return data


    def get_class_revenue_summary_formatted(self, clsID, date, quick_stats=True):
        """
        Format output from self.get_class_revenue_summary
        :param clsID: db.classes.id
        :param date: datetime.date
        :param quickstats: boolean
        :return: html table
        """
        T = current.T
        represent_float_as_amount = current.globalenv['represent_float_as_amount']

        revenue = self.get_class_revenue_summary(
            clsID=clsID,
            date=date,
            quick_stats=quick_stats
        )

        print revenue

        # {'dropin': {'membership': {'count': 0, 'amount': 0}, 'no_membership': {'count': 0, 'amount': 15.0}},
        #  'complementary': {'count': 0, 'amount': 0},
        #  'subscriptions': {'2 classes a week for a year': {'count': 1, 'amount': 7.0, 'total': 7.0},
        #                    '1 class a week ': {'count': 4, 'amount': 7.0, 'total': 28.0},
        #                    '1 class a week ODS member ': {'count': 2, 'amount': 7.0, 'total': 14.0},
        #                    '2 classes a week ': {'count': 1, 'amount': 7.0, 'total': 7.0}}, 'classcards': {},
        #  'trial': {'membership': {'count': 0, 'amount': 0}, 'no_membership': {'count': 0, 'amount': 15.0}},
        #  'total': {'count': 8, 'amount': 56.0}}


        header = THEAD(TR(
            TH(T('Type')),
            TH(T('Amount')),
            TH(T('Attendance count')),
            TH(T('Total')),
        ))

        trial_without_membership = TR(
            TD(T('Trial without membership')),
            TD(represent_float_as_amount(revenue['trial']['no_membership']['amount'])),
            TD(revenue['trial']['no_membership']['count']),
            TD(represent_float_as_amount(
                revenue['trial']['no_membership']['amount'] * revenue['trial']['no_membership']['count']
            )),
        )

        trial_with_membership =  TR(
            TD(T('Trial with membership')),
            TD(represent_float_as_amount(revenue['trial']['membership']['amount'])),
            TD(revenue['trial']['membership']['count']),
            TD(represent_float_as_amount(
                revenue['trial']['membership']['amount'] * revenue['trial']['membership']['count']
            )),
        )

        dropin_without_membership = TR(
            TD(T('Drop-in without membership')),
            TD(represent_float_as_amount(revenue['dropin']['no_membership']['amount'])),
            TD(revenue['dropin']['no_membership']['count']),
            TD(represent_float_as_amount(
                revenue['dropin']['no_membership']['amount'] * revenue['dropin']['no_membership']['count']
            )),
        )

        dropin_with_membership =  TR(
            TD(T('Drop-in with membership')),
            TD(represent_float_as_amount(revenue['dropin']['membership']['amount'])),
            TD(revenue['dropin']['membership']['count']),
            TD(represent_float_as_amount(
                revenue['dropin']['membership']['amount'] * revenue['dropin']['membership']['count']
            )),
        )
        
        

        table = TABLE(
            header,
            trial_without_membership,
            trial_with_membership,
            dropin_without_membership,
            dropin_with_membership,
            _class='table table-striped table-hover'
        )

        return table




#     className = "table" >
#     < thead >
#     < tr >
#     < th > {intl.formatMessage({id: "app.pos.checkin.revenue.list.attendance_type"})} < / th >
#     < th > {intl.formatMessage({id: "app.general.strings.amount"})} < / th >
#     < th > {intl.formatMessage({id: "app.general.strings.count"})} < / th >
#     < th > {intl.formatMessage({id: "app.general.strings.total"})} < / th >
#
# < / tr >
# < / thead >
# < tbody >
# < tr >
# < td > {intl.formatMessage({id: "app.pos.checkin.revenue.list.twom"})} < / td >
# < td > {currency_symbol}
# {' '}
# {revenue.trial.no_membership.amount.toFixed(2)} < / td >
# < td > {revenue.trial.no_membership.count} < / td >
# < td > {currency_symbol}
# {' '}
# {(revenue.trial.no_membership.amount * revenue.trial.no_membership.count).toFixed(2)} < / td >
# < / tr >
# < tr >
# < td > {intl.formatMessage({id: "app.pos.checkin.revenue.list.twm"})} < / td >
# < td > {currency_symbol}
# {' '}
# {revenue.trial.membership.amount.toFixed(2)} < / td >
# < td > {revenue.trial.membership.count} < / td >
# < td > {currency_symbol}
# {' '}
# {(revenue.trial.membership.amount * revenue.trial.membership.count).toFixed(2)} < / td >
# < / tr >
# < tr >
# < td > {intl.formatMessage({id: "app.pos.checkin.revenue.list.diwm"})} < / td >
# < td > {currency_symbol}
# {' '}
# {revenue.dropin.no_membership.amount.toFixed(2)} < / td >
# < td > {revenue.dropin.no_membership.count} < / td >
# < td > {currency_symbol}
# {' '}
# {(revenue.dropin.no_membership.amount * revenue.dropin.no_membership.count).toFixed(2)} < / td >
# < / tr >
# < tr >
# < td > {intl.formatMessage({id: "app.pos.checkin.revenue.list.diwom"})} < / td >
# < td > {currency_symbol}
# {' '}
# {revenue.dropin.membership.amount.toFixed(2)} < / td >
# < td > {revenue.dropin.membership.count} < / td >
# < td > {currency_symbol}
# {' '}
# {(revenue.dropin.membership.amount * revenue.dropin.membership.count).toFixed(2)} < / td >
# < / tr >
# {Object.keys(revenue.classcards).sort().map((key, index) = >
# < tr
# key = {v4()} >
#       < td > {key} < / td >
#                        < td > {currency_symbol}
# {' '}
# {revenue.classcards[key].amount.toFixed(2)} < / td >
#                                                 < td > {revenue.classcards[key].count} < / td >
#                                                                                            < td > {currency_symbol}
# {' '}
# {revenue.classcards[key].total.toFixed(2)} < / td >
#                                                < / tr >
# )}
# {Object.keys(revenue.subscriptions).sort().map((key, index) = >
# < tr
# key = {v4()} >
#       < td > {key} < / td >
#                        < td > {currency_symbol}
# {' '}
# {revenue.subscriptions[key].amount.toFixed(2)} < / td >
#                                                    < td > {revenue.subscriptions[key].count} < / td >
#                                                                                                  < td > {
#                                                                                                  currency_symbol}
# {' '}
# {revenue.subscriptions[key].total.toFixed(2)} < / td >
#                                                   < / tr >
# )}
#
# < / tbody >
# < tfoot >
# < tr >
# < th > {intl.formatMessage({id: "app.general.strings.total"})} < / th >
# < th > < / th >
# < th > {revenue.total.count} < / th >
# < th > {currency_symbol}
# {' '}
# {revenue.total.amount.toFixed(2)} < / th >
# < / tr >
# < / tfoot >
# < / table >
# < / div >
# < / div >
#
# export
# default
# RevenueList



    def get_class_revenue_rows(self, clsID, date):
        """
        :param clsID: db.classes.id
        :param date: Class date
        :return: All customers attending a class (db.customers_attendance.ALL & db.customers_subscriptions.ALL)
        """
        db = current.db

        left = [db.customers_classcards.on(
                    db.customers_classcards.id == db.classes_attendance.customers_classcards_id),
                db.school_classcards.on(
                    db.customers_classcards.school_classcards_id == db.school_classcards.id
                ),
                db.customers_subscriptions.on(
                    db.customers_subscriptions.id == db.classes_attendance.customers_subscriptions_id),
                db.school_subscriptions.on(
                    db.customers_subscriptions.school_subscriptions_id == db.school_subscriptions.id
                ),
                db.auth_user.on(db.classes_attendance.auth_customer_id == db.auth_user.id),
        ]
        query = (db.classes_attendance.classes_id == clsID) & \
                (db.classes_attendance.ClassDate == date) & \
                (db.classes_attendance.BookingStatus != 'cancelled')
        rows = db(query).select(db.auth_user.ALL,
                                db.classes_attendance.ALL,
                                db.customers_subscriptions.ALL,
                                db.school_subscriptions.ALL,
                                db.customers_classcards.ALL,
                                db.school_classcards.ALL,
                                left=left,
                                orderby=db.auth_user.display_name)

        return rows


    def get_class_revenue_classcard(self, row):
        """
            :param row: row from db.classes_attendance with left join on db.customers_subscriptions
            :return: Revenue for class taken on a card
        """
        from os_invoice import Invoice

        ccdID = row.classes_attendance.customers_classcards_id
        classcard = CustomerClasscard(ccdID)

        query = (db.invoices_customers_classcards.customers_classcards_id == ccdID)
        rows = db(query).select(db.invoices_customers_classcards.ALL)

        if not rows:
            revenue_in_vat = 0
            revenue_ex_vat = 0
            revenue_vat = 0
        else:
            row = rows.first()
            invoice = Invoice(row.invoices_id)
            amounts = invoice.get_amounts()

            price_in_vat = amounts.TotalPriceVAT
            price_ex_vat = amounts.TotalPrice

            # Divide by classes taken on card
            if classcard.unlimited:
                # Count all classes taken on card
                query = (db.classes_attendance.customers_classcards_id == ccdID)
                count_classes = db(query).count()

                revenue_in_vat = price_in_vat / count_classes
                revenue_ex_vat = price_ex_vat / count_classes
                revenue_vat = revenue_in_vat - revenue_ex_vat
            else:
                revenue_in_vat = price_in_vat / classcard.classes
                revenue_ex_vat = price_ex_vat / classcard.classes
                revenue_vat = revenue_in_vat - revenue_ex_vat

        return dict(revenue_in_vat=revenue_in_vat,
                    revenue_ex_vat=revenue_ex_vat,
                    revenue_vat=revenue_vat)

