"""Offscreen layout checks; no computer-use automation or network access."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
import pytest
from PySide6.QtCore import QRect
from innoforia_tally_connector.ui.workspace import Workspace


@pytest.mark.parametrize("width,height,points", [(960,650,10), (1100,700,13), (1280,800,15)])
def test_scaled_activity_overflow_scrolls_without_growing_window(qtbot, width, height, points):
    window = Workspace(); window.quitting = True; qtbot.addWidget(window)
    font = window.font(); font.setPointSize(points); window.setFont(font)
    window.identity.setText("Connected: verified Bahi business and Tally company with a long identity and company GUID")
    window.resize(width, height)
    window.tabs.setCurrentIndex(1)
    window.advanced.setChecked(True)
    window.advanced_tabs.setCurrentIndex(1)
    window.saved_details.setPlainText("Saved identity evidence\n" * 50)
    window.show(); qtbot.wait(20)
    assert window.minimumSizeHint().height() < height
    assert window.height() <= height
    assert window.width() <= width
    scroll = window.page_scrolls[1]
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.ensureWidgetVisible(window.technical.reconcile)
    qtbot.wait(10)
    point = window.technical.reconcile.mapTo(scroll.viewport(), window.technical.reconcile.rect().center())
    assert scroll.viewport().rect().contains(point)
    status = window.status.mapTo(window, window.status.rect().center())
    assert window.rect().contains(status)
    # Settings save stays reachable even when its content is wider/taller.
    window.tabs.setCurrentIndex(2)
    settings = window.page_scrolls[2]
    settings.ensureWidgetVisible(window.save_policy)
    qtbot.wait(10)
    point = window.save_policy.mapTo(settings.viewport(), window.save_policy.rect().center())
    assert settings.viewport().rect().contains(point)
    assert window.height() <= height


def test_initial_size_respects_available_logical_screen_area(qtbot, monkeypatch):
    monkeypatch.setattr(Workspace, "screen", lambda _: SimpleNamespace(availableGeometry=lambda: QRect(0,0,1024,720)))
    window = Workspace(); window.quitting = True; qtbot.addWidget(window)
    assert window.width() <= 984 and window.height() <= 640


def test_open_activity_starts_at_summary_and_keeps_legacy_details_collapsed(qtbot):
    from innoforia_tally_connector.domain.experiments import Direction
    window=Workspace();window.quitting=True;qtbot.addWidget(window)
    calls=[];window.send=lambda kind,**kwargs:calls.append((kind,kwargs))
    item=SimpleNamespace(source=SimpleNamespace(content=SimpleNamespace(name='SSS BUILDING PVT LTD')),
        status='SUCCEEDED',result=SimpleNamespace(target=SimpleNamespace(identity='283')),
        preview=SimpleNamespace(decisions=[SimpleNamespace(field='phone',status='excluded'),SimpleNamespace(field='gstin',status='excluded')]))
    window.current_batch=SimpleNamespace(direction=Direction.TO_BAHI,state='SUCCEEDED',items=(item,))
    window.resize(960,650);window.show();window.tabs.setCurrentIndex(1)
    window.advanced.setChecked(True);qtbot.wait(20)
    scroll=window.page_scrolls[1];scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    window.open_activity();qtbot.wait(20)
    assert window.tabs.currentIndex()==1 and not window.advanced.isChecked()
    assert not window.advanced_tabs.isVisible() and scroll.verticalScrollBar().value()==0
    assert 'SSS BUILDING PVT LTD: SUCCEEDED' in window.activity_summary.text()
    assert 'Bahi ID 283' in window.activity_summary.text()
    assert 'phone, gstin' in window.activity_summary.text()
    assert all(kind in {'BATCH_LIST','SAVED','ACTIVITY'} for kind,_ in calls)
    window.advanced.setChecked(True)
    assert window.advanced_tabs.isVisible()  # Evidence/recovery remain available.
    window.current_batch=None;window.open_activity()
    assert not window.activity_summary.isVisible() and not window.activity_summary.text()
