"""
Authoritative data source collectors for long-term forecasting.
Includes government statistical agencies, international organizations, and research institutions.
"""

from .census_collector import CensusBureauCollector
from .cia_factbook_collector import CIAFactbookCollector
from .think_tank_collector import ThinkTankCollector
from .un_data_collector import UNDataCollector
from .world_bank_collector import WorldBankCollector

__all__ = [
    'CensusBureauCollector',
    'WorldBankCollector',
    'UNDataCollector',
    'ThinkTankCollector',
    'CIAFactbookCollector'
]
