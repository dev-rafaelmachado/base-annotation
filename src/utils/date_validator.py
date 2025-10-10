"""
Validação e normalização de datas
"""
import re
import calendar
from datetime import datetime
from typing import Tuple, Optional


class DateValidator:
    """Valida e normaliza datas em diferentes formatos"""

    def normalize(self, date_str: str) -> Tuple[Optional[str], bool]:
        """
        Normaliza data para formato YYYY-MM-DD

        Aceita:
        - DD/MM/YYYY ou DD/MM/YY
        - DDMMYYYY
        - DDMMYY
        - MM/YYYY ou MM/YY (assume último dia do mês)
        - MMYYYY (assume último dia do mês)
        - MMYY (assume último dia do mês)

        Returns:
            (data_normalizada, é_válida)
        """
        date_str = date_str.strip()

        # Padrão 1: DD/MM/YYYY ou DD/MM/YY
        result = self._try_format_slash(date_str)
        if result[1]:
            return result

        # Padrão 2: DDMMYYYY (8 dígitos)
        result = self._try_format_8digits(date_str)
        if result[1]:
            return result

        # Padrão 3: DDMMYY (6 dígitos)
        result = self._try_format_6digits(date_str)
        if result[1]:
            return result

        # Padrão 4: MM/YYYY ou MM/YY (sem dia - assume último dia do mês)
        result = self._try_format_slash_no_day(date_str)
        if result[1]:
            return result

        # Padrão 5: MMYYYY (6 dígitos sem dia - assume último dia do mês)
        result = self._try_format_6digits_no_day(date_str)
        if result[1]:
            return result

        # Padrão 6: MMYY (4 dígitos sem dia - assume último dia do mês)
        result = self._try_format_4digits_no_day(date_str)
        if result[1]:
            return result

        return None, False

    def _get_last_day_of_month(self, year: int, month: int) -> int:
        """Retorna o último dia do mês para um ano e mês específicos"""
        # calendar.monthrange retorna (dia_da_semana_primeiro_dia, ultimo_dia)
        return calendar.monthrange(year, month)[1]

    def _try_format_slash(self, date_str: str) -> Tuple[Optional[str], bool]:
        """Tenta formato DD/MM/YYYY ou DD/MM/YY"""
        match = re.match(r'^(\d{2})/(\d{2})/(\d{2,4})$', date_str)
        if not match:
            return None, False

        day, month, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"

        return self._validate_date(year, month, day)

    def _try_format_8digits(self, date_str: str) -> Tuple[Optional[str], bool]:
        """Tenta formato DDMMYYYY"""
        match = re.match(r'^(\d{2})(\d{2})(\d{4})$', date_str)
        if not match:
            return None, False

        day, month, year = match.groups()
        return self._validate_date(year, month, day)

    def _try_format_6digits(self, date_str: str) -> Tuple[Optional[str], bool]:
        """Tenta formato DDMMYY"""
        match = re.match(r'^(\d{2})(\d{2})(\d{2})$', date_str)
        if not match:
            return None, False

        day, month, year = match.groups()
        year = f"20{year}"
        return self._validate_date(year, month, day)

    def _try_format_slash_no_day(self, date_str: str) -> Tuple[Optional[str], bool]:
        """Tenta formato MM/YYYY ou MM/YY (sem dia - assume último dia do mês)"""
        match = re.match(r'^(\d{2})/(\d{2,4})$', date_str)
        if not match:
            return None, False

        month, year = match.groups()
        if len(year) == 2:
            year = f"20{year}"

        # Calcula último dia do mês
        year_int = int(year)
        month_int = int(month)

        # Valida mês
        if month_int < 1 or month_int > 12:
            return None, False

        last_day = self._get_last_day_of_month(year_int, month_int)
        day = str(last_day).zfill(2)

        return self._validate_date(year, month, day)

    def _try_format_6digits_no_day(self, date_str: str) -> Tuple[Optional[str], bool]:
        """Tenta formato MMYYYY (6 dígitos sem dia - assume último dia do mês)"""
        match = re.match(r'^(\d{2})(\d{4})$', date_str)
        if not match:
            return None, False

        month, year = match.groups()

        # Calcula último dia do mês
        year_int = int(year)
        month_int = int(month)

        # Valida mês
        if month_int < 1 or month_int > 12:
            return None, False

        last_day = self._get_last_day_of_month(year_int, month_int)
        day = str(last_day).zfill(2)

        return self._validate_date(year, month, day)

    def _try_format_4digits_no_day(self, date_str: str) -> Tuple[Optional[str], bool]:
        """Tenta formato MMYY (4 dígitos sem dia - assume último dia do mês)"""
        match = re.match(r'^(\d{2})(\d{2})$', date_str)
        if not match:
            return None, False

        month, year = match.groups()
        year = f"20{year}"

        # Calcula último dia do mês
        year_int = int(year)
        month_int = int(month)

        # Valida mês
        if month_int < 1 or month_int > 12:
            return None, False

        last_day = self._get_last_day_of_month(year_int, month_int)
        day = str(last_day).zfill(2)

        return self._validate_date(year, month, day)

    def _validate_date(self, year: str, month: str, day: str) -> Tuple[Optional[str], bool]:
        """Valida se a data é real"""
        try:
            datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
            return f"{year}-{month}-{day}", True
        except ValueError:
            return None, False
