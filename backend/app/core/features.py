from enum import StrEnum


class Feature(StrEnum):
    TIMECLOCK = "timeclock"
    HACCP_TEMPERATURE = "haccp_temperature"
    CLEANING = "cleaning"
    RECEPTIONS = "receptions"
    NONCONFORMITIES = "nonconformities"
    SUPPLIERS = "suppliers"
    OPERATORS = "operators"
