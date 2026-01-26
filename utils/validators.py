import re
from datetime import datetime


def is_valid_date(date_string):
    """
    Проверяет, является ли строка корректной датой в формате ДД.ММ.ГГГГ
    """
    pattern = r'^\d{2}\.\d{2}\.\d{4}$'
    if not re.match(pattern, date_string):
        return False

    try:
        day, month, year = map(int, date_string.split('.'))

        if year < 1900 or year > datetime.now().year:
            return False
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False

        if month in [4, 6, 9, 11] and day > 30:
            return False
        if month == 2:
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                if day > 29:
                    return False
            else:
                if day > 28:
                    return False

        input_date = datetime(year, month, day)
        if input_date > datetime.now():
            return False

        return True
    except ValueError:
        return False