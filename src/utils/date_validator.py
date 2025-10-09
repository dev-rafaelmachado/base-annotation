"""
Validação e normalização de datas
"""
import re
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

        return None, False

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

    def _validate_date(self, year: str, month: str, day: str) -> Tuple[Optional[str], bool]:
        """Valida se a data é real"""
        try:
            datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
            return f"{year}-{month}-{day}", True
        except ValueError:
            return None, False
