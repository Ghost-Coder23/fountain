from calendar import monthrange
from datetime import date

from academics.models import AcademicYear
from results.models import Term


def add_months(value, offset):
    month_index = value.month - 1 + offset
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def month_bounds(year, month):
    start = date(year, month, 1)
    return start, date(year, month, monthrange(year, month)[1])


def parse_period_key(period_key, today=None):
    today = today or date.today()
    if period_key == 'term':
        return {'scope': 'term', 'key': 'term'}
    if period_key == 'year':
        return {'scope': 'year', 'key': 'year'}
    if period_key:
        try:
            year_text, month_text = period_key.split('-', 1)
            year = int(year_text)
            month = int(month_text)
            if 1 <= month <= 12:
                start, end = month_bounds(year, month)
                return {
                    'scope': 'month',
                    'key': f'{year}-{month:02d}',
                    'year': year,
                    'month': month,
                    'start': start,
                    'end': end,
                    'label': start.strftime('%B %Y'),
                }
        except (TypeError, ValueError):
            pass

    start, end = month_bounds(today.year, today.month)
    return {
        'scope': 'month',
        'key': f'{today.year}-{today.month:02d}',
        'year': today.year,
        'month': today.month,
        'start': start,
        'end': end,
        'label': start.strftime('%B %Y'),
    }


def get_selected_billing_period(request, school, today=None):
    today = today or date.today()
    current_term = Term.objects.filter(academic_year__school=school, is_current=True).first()
    current_year = AcademicYear.objects.filter(school=school, is_current=True).first()
    selected = parse_period_key(request.GET.get('period'), today=today)

    if selected['scope'] == 'term':
        selected['term'] = current_term
        selected['academic_year'] = current_year
        selected['label'] = f'Whole Term - {current_term.name}' if current_term else 'Whole Term'
        if current_term:
            selected['start'] = current_term.start_date
            selected['end'] = current_term.end_date
    elif selected['scope'] == 'year':
        # Whole academic year selection
        selected['term'] = None
        selected['academic_year'] = current_year
        selected['label'] = f'Whole Academic Year - {current_year.name}' if current_year else 'Whole Academic Year'
        if current_year:
            selected['start'] = current_year.start_date
            selected['end'] = current_year.end_date
    else:
        selected['term'] = Term.objects.filter(
            academic_year__school=school,
            start_date__lte=selected['start'],
            end_date__gte=selected['start'],
        ).first() or current_term
        selected['academic_year'] = AcademicYear.objects.filter(
            school=school,
            start_date__lte=selected['start'],
            end_date__gte=selected['start'],
        ).first() or current_year

    # Offer both Whole Term and Whole Academic Year as top-level options so users can choose
    options = [
        {'key': 'term', 'label': 'Whole Term'},
        {'key': 'year', 'label': 'Whole Academic Year'},
    ]
    option_months = []
    if current_term:
        cursor = current_term.start_date.replace(day=1)
        end_month = current_term.end_date.replace(day=1)
        while cursor <= end_month:
            option_months.append(cursor)
            cursor = add_months(cursor, 1)
    elif current_year:
        cursor = current_year.start_date.replace(day=1)
        end_month = current_year.end_date.replace(day=1)
        while cursor <= end_month:
            option_months.append(cursor)
            cursor = add_months(cursor, 1)
    else:
        option_months = [add_months(today.replace(day=1), offset) for offset in range(-2, 4)]

    if selected['scope'] == 'month' and selected.get('start') not in option_months:
        option_months.append(selected['start'])
        option_months.sort()

    for item in option_months:
        options.append({'key': f'{item.year}-{item.month:02d}', 'label': item.strftime('%B %Y')})

    selected['options'] = options
    return selected


def filter_invoices_for_period(invoices, period):
    if period['scope'] == 'term':
        term = period.get('term')
        if term:
            return invoices.filter(term=term)
        return invoices.none()
    if period['scope'] == 'year':
        ay = period.get('academic_year')
        if ay:
            # invoices within academic year range
            return invoices.filter(billing_period_start__gte=ay.start_date, billing_period_start__lte=ay.end_date)
        return invoices.none()
    return invoices.filter(billing_year=period['year'], billing_month=period['month'])


def period_query_string(period):
    return f"period={period['key']}"
