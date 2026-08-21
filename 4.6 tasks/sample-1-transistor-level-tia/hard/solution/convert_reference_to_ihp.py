#!/usr/bin/env python3
"""Convert the archived generic-device TIA reference to IHP SG13G2 devices."""

from __future__ import annotations

import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "reference-generic-baseline.cir"
OUTPUT = HERE / "reference.cir"


def engineering_microns(raw: str) -> float:
    value = raw.casefold()
    if value.endswith("u"):
        return float(value[:-1])
    return float(value)


def fmt(value: float) -> str:
    return f"{value:.12g}"


def convert_mos(tokens: list[str]) -> str:
    name, drain, gate, source, bulk, generic = tokens[:6]
    parameters = {
        key.casefold(): value
        for token in tokens[6:]
        if "=" in token
        for key, value in [token.split("=", 1)]
    }
    width = engineering_microns(parameters["w"])
    length = max(0.45, engineering_microns(parameters["l"]))
    fingers = max(1, min(64, round(width / 2.0)))
    wrapper = "sg13_hv_nmos" if generic.casefold() == "nmos" else "sg13_hv_pmos"
    return (
        f"X{name} {drain} {gate} {source} {bulk} {wrapper} "
        f"w={fmt(width)}u l={fmt(length)}u ng={fingers} m=1 rfmode=1"
    )


def convert_bjt(tokens: list[str]) -> str:
    name, collector, base, emitter, generic = tokens[:5]
    area = 1
    for token in tokens[5:]:
        if token.casefold().startswith("area="):
            area = max(1, int(round(float(token.split("=", 1)[1]))))
    if generic.casefold() in {"qn", "qbuf"}:
        upper_name = name.upper()
        if generic.casefold() == "qbuf":
            nx = area
        elif upper_name.endswith("_AMP"):
            nx = max(1, area // 2)
        elif upper_name.endswith("_EF"):
            nx = area
        elif re.search(r"_XVGA[12]_7$|_XVGA[12]_8$", upper_name):
            nx = area
        elif re.search(r"_XAGC_SF[PN]$", upper_name):
            nx = area
        else:
            nx = 1
        high_voltage = upper_name.endswith(("_SFPSINK", "_SFNSINK"))
        model = "npn13G2v" if high_voltage else "npn13G2"
        maximum_nx = 4 if high_voltage else 10
        return (
            f"X{name} {collector} {base} {emitter} 0 {model} "
            f"Nx={min(nx, maximum_nx)} selft=0"
        )
    # SG13G2's parasitic PNP has a nominal beta near unity and cannot provide
    # the paper-style slow cancellation amplifier. Use the process 3.3 V PMOS
    # as the physically supported high-side differential device instead.
    return (
        f"X{name} {collector} {base} {emitter} vcc sg13_hv_pmos "
        f"w={area}u l=0.45u ng={max(1, area)} m=1 rfmode=0"
    )


def main() -> None:
    converted: list[str] = []
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            converted.append(raw)
            continue
        if stripped.casefold().startswith(".model "):
            continue
        tokens = stripped.split()
        if tokens[0][0].casefold() == "m":
            converted.append(convert_mos(tokens))
        elif tokens[0][0].casefold() == "q":
            converted.append(convert_bjt(tokens))
        else:
            converted.append(raw)
    text = "\n".join(converted).rstrip() + "\n"
    text = re.sub(
        r"\* Canonical paper-matched production topology\.",
        "* IHP SG13G2 SiGe BiCMOS implementation of the paper-level topology.",
        text,
    )
    text = text.replace(
        "* Fully flattened: no compound X devices or subcircuit hierarchy remain.",
        "* Flat design hierarchy; X instances are only pinned IHP PDK primitives.",
    )
    text = text.replace("R_XVGA1_E XVGA1__e1 XVGA1__e2 93", "R_XVGA1_E XVGA1__e1 XVGA1__e2 5")
    text = text.replace("R_XVGA2_E XVGA2__e1 XVGA2__e2 93", "R_XVGA2_E XVGA2__e1 XVGA2__e2 5")
    text = text.replace("C_XVGA1_E XVGA1__e1 XVGA1__e2 1a", "C_XVGA1_E XVGA1__e1 XVGA1__e2 50f")
    for stage in ("XVGA1", "XVGA2"):
        for side, node in (("CL", "nl"), ("CR", "nr")):
            original = f"R_{stage}_{side} vcc {stage}__{node} 270"
            peaked = (
                f"L_{stage}_{side} vcc {stage}__peak_{node} 2.7n\n"
                f"R_{stage}_{side} {stage}__peak_{node} {stage}__{node} 400"
            )
            text = text.replace(original, peaked)
    text = text.replace("R_XBUF_E XBUF__e1 XBUF__e2 28.8", "R_XBUF_E XBUF__e1 XBUF__e2 20")
    text = text.replace("RIFBTOP vcc ifbias 5k", "RIFBTOP vcc ifbias 700")
    text = text.replace("RIBTOP vcc ifbase 3k", "RIBTOP vcc ifbase 400")
    text = text.replace("R_XTIAP_REFINTOP vcc XTIAP__in_ref_gate 144.7k", "R_XTIAP_REFINTOP vcc XTIAP__in_ref_gate 100k")
    text = text.replace("R_XTIAN_REFINTOP vcc XTIAN__in_ref_gate 144.7k", "R_XTIAN_REFINTOP vcc XTIAN__in_ref_gate 100k")
    text = text.replace(
        "XM_CANCEL_P inp XTIAP__cancel_gate 0 0 sg13_hv_nmos w=25u",
        "XM_CANCEL_CAS_P inp oa XTIAP__cancel_d 0 sg13_hv_nmos w=20u l=0.45u ng=10 m=1 rfmode=1\n"
        "XM_CANCEL_P XTIAP__cancel_d XTIAP__cancel_gate 0 0 sg13_hv_nmos w=100u",
    )
    text = text.replace(
        "XM_CANCEL_N inn XTIAN__cancel_gate 0 0 sg13_hv_nmos w=25u",
        "XM_CANCEL_CAS_N inn oa XTIAN__cancel_d 0 sg13_hv_nmos w=20u l=0.45u ng=10 m=1 rfmode=1\n"
        "XM_CANCEL_N XTIAN__cancel_d XTIAN__cancel_gate 0 0 sg13_hv_nmos w=100u",
    )
    text = text.replace("R_XTIAP_PBIAS XTIAP__pbias 0 3k", "R_XTIAP_PBIAS XTIAP__pbias 0 100k")
    text = text.replace("R_XTIAN_PBIAS XTIAN__pbias 0 3k", "R_XTIAN_PBIAS XTIAN__pbias 0 100k")
    text = text.replace("R_XTIAP_POUT1 XTIAP__nvin 0 3.1k", "R_XTIAP_POUT1 XTIAP__nvin 0 100k")
    text = text.replace("R_XTIAP_POUT2 XTIAP__cancel_gate 0 3.1k", "R_XTIAP_POUT2 XTIAP__cancel_gate 0 100k")
    text = text.replace("R_XTIAN_POUT1 XTIAN__nvin 0 3.1k", "R_XTIAN_POUT1 XTIAN__nvin 0 100k")
    text = text.replace("R_XTIAN_POUT2 XTIAN__cancel_gate 0 3.1k", "R_XTIAN_POUT2 XTIAN__cancel_gate 0 100k")
    text = text.replace("R_XTIAP_NL1 vcc XTIAP__nlsense 2.2k", "R_XTIAP_NL1 vcc XTIAP__nlsense 2.5k")
    text = text.replace("R_XTIAN_NL1 vcc XTIAN__nlsense 2.2k", "R_XTIAN_NL1 vcc XTIAN__nlsense 2.5k")
    for stage in ("XVGA1", "XVGA2"):
        text = text.replace(
            f"XM_{stage}_BIAS3 vga{stage[-1]}p {stage}__nbias 0 0 sg13_hv_nmos w=38u l=0.45u ng=19 m=1 rfmode=1",
            f"XM_{stage}_BIAS3 vga{stage[-1]}p {stage}__nbias 0 0 sg13_hv_nmos w=3u l=0.45u ng=19 m=1 rfmode=1",
        )
        text = text.replace(
            f"XM_{stage}_BIAS4 vga{stage[-1]}n {stage}__nbias 0 0 sg13_hv_nmos w=38u l=0.45u ng=19 m=1 rfmode=1",
            f"XM_{stage}_BIAS4 vga{stage[-1]}n {stage}__nbias 0 0 sg13_hv_nmos w=3u l=0.45u ng=19 m=1 rfmode=1",
        )
    # The PDK treats w as total gate width.  These finger widths remain above
    # its 0.15 um minimum while reducing follower current enough for HBT VCE.
    text = text.replace(
        "XM_XVGA2_BIAS3 vga2p XVGA2__nbias 0 0 sg13_hv_nmos w=3u l=0.45u ng=19",
        "XM_XVGA2_BIAS3 vga2p XVGA2__nbias 0 0 sg13_hv_nmos w=1.8u l=0.45u ng=12",
    )
    text = text.replace(
        "XM_XVGA2_BIAS4 vga2n XVGA2__nbias 0 0 sg13_hv_nmos w=3u l=0.45u ng=19",
        "XM_XVGA2_BIAS4 vga2n XVGA2__nbias 0 0 sg13_hv_nmos w=1.8u l=0.45u ng=12",
    )
    text = text.replace(
        "CPKDINP finalp pkdinp 6.8p",
        "RPKDTAPP finalp pkdtap_p 2k\nCPKDINP pkdtap_p pkdinp 6.8p",
    )
    text = text.replace(
        "CPKDINN finaln pkdinn 6.8p",
        "RPKDTAPN finaln pkdtap_n 2k\nCPKDINN pkdtap_n pkdinn 6.8p",
    )
    text = text.replace(
        "XQ_XPKD_8 vcc pkdinn XPKD__e8 0 npn13G2 Nx=1 selft=0",
        "R_PKDVCC vcc pkdvcc 500\n"
        "C_PKDVCC pkdvcc 0 10p\n"
        "XQ_XPKD_8 pkdvcc pkdinn XPKD__e8 0 npn13G2 Nx=1 selft=0",
    )
    text = text.replace(
        "XQ_XPKD_7 vcc pkdinp XPKD__e7 0 npn13G2 Nx=1 selft=0",
        "XQ_XPKD_7 pkdvcc pkdinp XPKD__e7 0 npn13G2 Nx=1 selft=0",
    )
    text = text.replace("R_XPKD_CL vcc detn 200", "R_XPKD_CL vcc detn 800")
    text = text.replace("R_XPKD_CR vcc detp 200", "R_XPKD_CR vcc detp 800")
    text = text.replace(
        "XQ_XTIAP_AMP tia_p inp 0 0 npn13G2 Nx=3 selft=0",
        "R_TIA_CASTOP vcc tia_casbias 16k\n"
        "R_TIA_CASBOT tia_casbias 0 17k\n"
        "C_TIA_CASBIAS tia_casbias 0 10p\n"
        "XQ_XTIAP_AMP XTIAP__casnode inp 0 0 npn13G2 Nx=3 selft=0\n"
        "XQ_XTIAP_CAS tia_p tia_casbias XTIAP__casnode 0 npn13G2 Nx=3 selft=0",
    )
    text = text.replace(
        "XQ_XTIAN_AMP tia_n inn 0 0 npn13G2 Nx=3 selft=0",
        "XQ_XTIAN_AMP XTIAN__casnode inn 0 0 npn13G2 Nx=3 selft=0\n"
        "XQ_XTIAN_CAS tia_n tia_casbias XTIAN__casnode 0 npn13G2 Nx=3 selft=0",
    )
    OUTPUT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
