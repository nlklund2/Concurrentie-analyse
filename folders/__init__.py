"""Foldermonitor — add-on op de concurrentiemonitor (docs/foldermonitor-plan.md).

Fase 0: bronconfiguratie, viewerdetectie en de validatie-CLI. De sweep
(mail → archief) en de extractie volgen in fase 1 en 2. Dit pakket leest
uitsluitend de FOLDERS_*-omgevingsvariabelen: de productiesleutels van de
scraper bereiken het bewust niet (plan §9.5).
"""
