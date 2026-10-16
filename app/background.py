"""Local decorative blockchain geometry, not transaction or verification evidence."""

from urllib.parse import quote

CHAIN_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1100" viewBox="0 0 1600 1100">
<defs>
  <linearGradient id="chain-light" x1="0" y1="0" x2="1" y2="1">
    <stop stop-color="#E0C477" stop-opacity=".42"/>
    <stop offset="1" stop-color="#BA963E" stop-opacity=".12"/>
  </linearGradient>
  <linearGradient id="block-face" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#555B5D" stop-opacity=".12"/>
    <stop offset="1" stop-color="#34383B" stop-opacity=".02"/>
  </linearGradient>
  <linearGradient id="gold-thread" x1="0" y1="1" x2="1" y2="0">
    <stop stop-color="#BA963E" stop-opacity=".06"/>
    <stop offset=".55" stop-color="#E0C477" stop-opacity=".28"/>
    <stop offset="1" stop-color="#C9A86A" stop-opacity=".06"/>
  </linearGradient>
</defs>
<g fill="none" stroke="url(#gold-thread)" stroke-width="1">
  <path d="M-100 990 C350 980 360 570 800 640 S1340 700 1690 310"/>
  <path d="M-100 980 C350 968 370 558 800 628 S1340 686 1690 296"/>
  <path d="M-100 970 C350 956 380 546 800 616 S1340 672 1690 282"/>
  <path d="M-100 960 C350 944 390 534 800 604 S1340 658 1690 268"/>
  <path d="M-100 950 C350 932 400 522 800 592 S1340 644 1690 254"/>
  <path d="M-100 940 C350 920 410 510 800 580 S1340 630 1690 240"/>
  <path d="M-100 930 C350 908 420 498 800 568 S1340 616 1690 226"/>
  <path d="M-100 920 C350 896 430 486 800 556 S1340 602 1690 212"/>
  <path d="M-100 910 C350 884 440 474 800 544 S1340 588 1690 198"/>
  <path d="M-100 900 C350 872 450 462 800 532 S1340 574 1690 184"/>
  <path d="M-100 890 C350 860 460 450 800 520 S1340 560 1690 170"/>
  <path d="M-100 880 C350 848 470 438 800 508 S1340 546 1690 156"/>
</g>
<g fill="none" stroke="url(#chain-light)" stroke-width="1">
  <path d="M950 110 L1075 170 L1220 120 L1360 185 L1510 130"/>
  <path d="M1075 170 L1095 355 L1230 420 L1390 360 L1510 470"/>
  <path d="M1230 420 L1130 555 L1270 620 L1460 565"/>
  <path d="M1095 355 L925 440 L840 620 L950 785 L1125 835"/>
  <path d="M50 730 L210 675 L350 755 L440 910 L620 975"/>
  <path d="M210 675 L245 500 L385 430"/>
  <path stroke-dasharray="3 9" d="M950 110 L925 440 M1220 120 L1230 420 M1360 185 L1390 360"/>
</g>
<g fill="url(#block-face)" stroke="url(#chain-light)" stroke-width="1.2">
  <path d="M1110 190 l92 -48 92 48 -92 48z M1110 190 v104 l92 48 92 -48 V190 M1202 238 v104"/>
  <path d="M1310 455 l64 -34 64 34 -64 34z M1310 455 v72 l64 34 64 -34 V455 M1374 489 v72"/>
  <path d="M130 780 l55 -29 55 29 -55 29z M130 780 v64 l55 29 55 -29 V780 M185 809 v64"/>
</g>
<g fill="#E0C477" fill-opacity=".28">
  <circle cx="950" cy="110" r="3"/><circle cx="1075" cy="170" r="4"/>
  <circle cx="1220" cy="120" r="3"/><circle cx="1360" cy="185" r="3"/>
  <circle cx="1095" cy="355" r="3"/><circle cx="1230" cy="420" r="4"/>
  <circle cx="1390" cy="360" r="3"/><circle cx="1130" cy="555" r="3"/>
  <circle cx="1270" cy="620" r="3"/><circle cx="925" cy="440" r="3"/>
  <circle cx="840" cy="620" r="3"/><circle cx="950" cy="785" r="3"/>
  <circle cx="210" cy="675" r="4"/><circle cx="350" cy="755" r="3"/>
  <circle cx="245" cy="500" r="3"/><circle cx="440" cy="910" r="3"/>
</g>
</svg>"""


def chain_background_url() -> str:
    return 'url("data:image/svg+xml,' + quote(CHAIN_SVG, safe="") + '")'
