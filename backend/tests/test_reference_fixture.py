from decimal import Decimal


def test_entrega_1_reference_months_sum_to_annual_limit_and_keep_closed_months():
    # Fixture documental sem titular, CPF, tarifa, clima ou medição real.
    monthly = [
        486000, 583200, 907200, 1296000, 712800, 648000,
        1123200, 0, 0, 810000, 583200, 874800,
    ]
    assert sum(monthly) == 8_024_400
    assert Decimal(monthly[7]) == Decimal(0)
    assert Decimal(monthly[8]) == Decimal(0)
