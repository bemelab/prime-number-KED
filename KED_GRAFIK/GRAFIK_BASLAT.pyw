# -*- coding: utf-8 -*-
"""PATİ KED GRAFİK programını siyah konsol penceresi OLMADAN açar (çift tıklayın; pythonw ile çalışır)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import KED_GRAFIK as grafik

if __name__ == '__main__':
    grafik.main()
