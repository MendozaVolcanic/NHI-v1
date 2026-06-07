"""
Tests del algoritmo NHI Landsat OLI (nhi_landsat.py).

Verifica que la logica replica el source GEE (nhi_tool_source.js) usando casos
fisicos construidos a mano, sin necesidad de datos reales ni red.

Correr: python test_nhi_landsat.py
"""
import numpy as np
from nhi_landsat import calcular_nhi_landsat, landsat_dn_to_radiance


def _arr(val):
    """Array 11x11 (>=100 px validos) lleno de val, con un pixel central editable."""
    return np.full((11, 11), float(val))


def _run(b400, b800, b1600, b2200):
    """Corre el algoritmo con un campo uniforme (todos los px iguales)."""
    mask = np.ones((11, 11), dtype=bool)
    return calcular_nhi_landsat(_arr(b400), _arr(b800), _arr(b1600), _arr(b2200), mask)


def test_dn_to_radiance():
    # L = mult*DN + add ; negativos se clipean a 0
    dn = np.array([[20000.0, 1000.0, 0.0]])
    mult, add = 0.01, -50.0
    r = landsat_dn_to_radiance(dn, mult, add)
    assert r[0, 0] == 0.01 * 20000 - 50      # 200-50 = 150 (positivo, sin clip)
    assert r[0, 1] == max(0.01 * 1000 - 50, 0)   # -40 -> clip 0
    assert r[0, 2] == 0.0                     # DN 0 -> -50 -> clip 0
    print("OK test_dn_to_radiance (lineal + clip negativos)")


def test_pixel_frio():
    # Superficie fria: radiancia solar decreciente b800>b1600>b2200, b400 alto
    r = _run(b400=80, b800=60, b1600=30, b2200=15)
    assert r["pixeles_calientes"] == 0, r
    assert not r["alerta"]
    print("OK test_pixel_frio (sin deteccion)")


def test_lava_caliente_swnir():
    # Lava: emision termica fuerte, b2200>b1600>b800, b400 bajo
    r = _run(b400=10, b800=8, b1600=50, b2200=80)
    assert r["pixeles_calientes"] == 121, r           # 11x11 todos hot
    assert r["pixeles_cond_b"] == 121, r              # SWNIR_L8 (high intensity)
    assert r["pixeles_cond_a"] == 0, r                # SWNIR tiene prioridad
    assert r["pixeles_extreme"] == 0, r
    print("OK test_lava_caliente_swnir (prioridad SWNIR sobre SWIR)")


def test_swir_moderado():
    # nhi_swir>0 pero nhi_swnir<=0  -> SWIR_L8 (mid-low intensity)
    r = _run(b400=10, b800=40, b1600=35, b2200=50)
    assert r["pixeles_cond_a"] == 121, r              # SWIR_L8
    assert r["pixeles_cond_b"] == 0, r
    print("OK test_swir_moderado (cond_a / SWIR_L8)")


def test_extreme_saturado():
    # Saturado: no swir/swnir, b1600>=74, b400<70
    r = _run(b400=10, b800=90, b1600=80, b2200=70)
    assert r["pixeles_extreme"] == 121, r
    assert r["pixeles_cond_a"] == 0 and r["pixeles_cond_b"] == 0, r
    print("OK test_extreme_saturado")


def test_nieve_brillante_rechazada():
    # Nieve: brillante en todo, b400 alto -> el test b400<70 debe RECHAZAR extreme
    r = _run(b400=90, b800=95, b1600=80, b2200=70)
    assert r["pixeles_calientes"] == 0, r             # b400>=70 bloquea extreme
    print("OK test_nieve_brillante_rechazada (test b400<70 funciona)")


def test_umbral_extreme_74_vs_70():
    # Diferencia clave con S2: OLI exige b1600>=74 (S2 usa 70).
    # b1600=72 NO debe gatillar extreme en OLI (en S2 si gatillaria).
    r = _run(b400=10, b800=90, b1600=72, b2200=70)
    assert r["pixeles_extreme"] == 0, "b1600=72 < 74 no debe ser EXTREME en OLI"
    r2 = _run(b400=10, b800=90, b1600=74, b2200=70)
    assert r2["pixeles_extreme"] == 121, "b1600=74 si debe ser EXTREME en OLI"
    print("OK test_umbral_extreme_74 (difiere de S2=70)")


def test_radiancia_sum_vs_max():
    r = _run(b400=10, b800=8, b1600=50, b2200=80)
    assert r["sum_b2200_radiance"] >= r["max_b2200_radiance"]   # suma N px >= max
    assert abs(r["sum_b2200_radiance"] - 121 * 80) < 1.0        # 121 px * 80
    print("OK test_radiancia_sum_vs_max")


if __name__ == "__main__":
    test_dn_to_radiance()
    test_pixel_frio()
    test_lava_caliente_swnir()
    test_swir_moderado()
    test_extreme_saturado()
    test_nieve_brillante_rechazada()
    test_umbral_extreme_74_vs_70()
    test_radiancia_sum_vs_max()
    print("\n=== TODOS LOS TESTS PASARON ===")
