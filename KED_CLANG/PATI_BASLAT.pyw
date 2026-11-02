# -*- coding: utf-8 -*-
"""PATİ KED taramasını siyah konsol penceresi OLMADAN açar (çift tıklayın; pythonw ile çalışır)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import PATI_5_10_TRILYON_HIZLI_UI as pati

if __name__ == '__main__':
    pati.main()
